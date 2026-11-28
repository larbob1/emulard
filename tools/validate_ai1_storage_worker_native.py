# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated actual storage worker native gate; no production registration."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)

def build(target, release):
    args = ["cargo", "test", "--locked", "-p", "victory-hle", "--lib", "--features",
            "diagnostics", "--no-run", "--message-format=json"]
    if release:
        args.append("--release")
    r = subprocess.run(args, cwd=target, capture_output=True, text=True,
                       errors="replace", timeout=2400, env=clean_env())
    if r.returncode:
        print((r.stdout + "\n" + r.stderr)[-20000:], flush=True)
        raise ValueError("test compile failed")
    artifacts = []
    for line in r.stdout.splitlines():
        obj = json.loads(line)
        if (obj.get("reason") == "compiler-artifact" and obj.get("executable")
                and obj.get("target", {}).get("name") == "victory_hle"
                and obj.get("profile", {}).get("test") is True):
            artifacts.append(Path(obj["executable"]).resolve())
    if len(artifacts) != 1 or not artifacts[0].is_file() or not artifacts[0].is_relative_to(target.resolve()):
        raise ValueError(f"unexpected test executables: {artifacts}")
    return artifacts[0]

REVIEWED = "673dcf96790d34e50e9aa15fbd238fbb87cbf4d5"
PINS = {
    "tools/prepare_storage_worker_native.py": "be3d72806fafeaeab17243d8a3456c8686e6652f",
    "probes/storage_worker_native.rs": "143131011a9be1cfa39fee828f5369489bfd3ffd",
    "docs/storage-worker-native.md": "f8c01f6173ee117f3dfd8926cf78f9fea26bdbbd",
    "tools/build_runtime.py": BUILDER,
}
DEST = "crates/victory-hle/src/modules/dstorage.rs"
POST = "59358fe65fbc835d86a6ddfa493dfacf943b0811"
PREFIX = "modules::dstorage::tests::storage_worker_native_"
CASE_KEYS = "index slot lane seq options source destination hr before after calls hits".split()
FINAL_KEYS = "cap spawned entered cases success failed delivered guards remaining_lanes staged".split()
def lf(data):
    return data.replace(b"\r\n", b"\n")

def clean_env():
    return {k:v for k,v in os.environ.items()
            if not k.upper().startswith(("VICTORY_", "RUST_TEST_", "AI5_", "AI6_"))
            and k.upper() not in ("CARGO_TARGET_DIR", "CARGO_BUILD_TARGET_DIR")}

def inventory(root):
    result = {}
    def walk(directory):
        for p in sorted(directory.iterdir()):
            rel = p.relative_to(root).as_posix()
            if rel == ".git":
                continue
            if p.is_symlink() or p.is_junction():
                raise ValueError("unexpected link in disposable checkout: " + rel)
            if p.is_dir():
                result[rel] = ("dir",)
                walk(p)
            elif p.is_file():
                with p.open("rb") as f:
                    result[rel] = ("file", hashlib.file_digest(f, "sha256").hexdigest())
            else:
                raise ValueError("unexpected path type: " + rel)
    walk(root)
    return result

def direct(args, target, env):
    try:
        p = subprocess.run(args, cwd=target, env=env, capture_output=True,
                           text=True, errors="replace", timeout=60)
    except subprocess.TimeoutExpired as exc:
        for label, stream in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            print(label + " (partial):", flush=True)
            if stream:
                print(stream.decode("utf-8", errors="replace") if isinstance(stream, bytes) else stream, flush=True)
        raise
    print("stdout:\n" + p.stdout, flush=True)
    print("stderr:\n" + p.stderr, flush=True)
    return p


def parse_row(line, prefix, keys, signed=()):
    pattern = prefix + "".join(" " + k + "=" + (r"(-?\d+)" if k in signed else r"(\d+)") for k in keys)
    m = re.fullmatch(pattern, line)
    if not m:
        raise ValueError("malformed receipt: " + line)
    return dict(zip(keys, map(int, m.groups())))

def parse_receipts(stderr, reuse):
    lines = [l for l in stderr.splitlines() if l.startswith("storage_worker_")]
    if len(lines) != 11:
        raise ValueError("expected ten case receipts and one terminal receipt")
    rows = [parse_row(l, "storage_worker_case", CASE_KEYS, ("hr",)) for l in lines[:10]]
    final = parse_row(lines[10], "storage_worker_final", FINAL_KEYS)
    options = [0,0,0,0,0,4194304,4194305,0,0,0]
    source = [4096,4096,16,4096,4096,4096,None,131072,4096,4096]
    dest = [4096,4096,8,4096,4096,4096,4096,131072,4096,4096]
    hr = [0,0,-2147024809,-2147024858,0,0,0,0,0,0]
    calls = [1,1,0,1,1,0,0,1,1,1]
    hits = [0,1,0,1,0,0,0,0,0,1]
    for i, row in enumerate(rows):
        if (row["index"],row["slot"],row["options"],row["destination"],row["hr"]) != (i,0,options[i],dest[i],hr[i]):
            raise ValueError("case identity/status")
        if source[i] is not None and row["source"] != source[i]:
            raise ValueError("source size")
        if not 0 < row["source"] < 2**32 or not 0 <= row["lane"] < 2**64 or not 0 <= row["seq"] < 2**64:
            raise ValueError("numeric range")
        if (row["lane"] == rows[0]["lane"]) != (i < 9):
            raise ValueError("lane identity")
        if i and row["seq"] <= rows[i-1]["seq"]:
            raise ValueError("sequence")
        if row["before"] != (rows[i-1]["after"] if i else 0):
            raise ValueError("capacity continuity")
        if not reuse:
            if any(row[k] for k in ("before","after","calls","hits")):
                raise ValueError("baseline used scratch")
        else:
            if (row["calls"],row["hits"]) != (calls[i],hits[i]) or not 0 <= row["after"] <= 65536:
                raise ValueError("scratch counters/cap")
            if i in (3,7):
                ok = row["after"] == 0
            elif i in (2,5,6):
                ok = row["after"] == row["before"]
            else:
                ok = row["after"] >= 4096
            if not ok:
                raise ValueError("scratch transition")
    expected = dict(zip(FINAL_KEYS, (65536 if reuse else 0,1,1,10,8,2,159744,160,0,0)))
    if final != expected:
        raise ValueError("terminal receipt")
    successes = [row for row in rows if row["hr"] == 0]
    if (len(successes),len(rows)-len(successes),sum(row["destination"] for row in successes)) != (final["success"],final["failed"],final["delivered"]):
        raise ValueError("terminal aggregate")
    return rows[6]["source"]

def run_exact(exe, target, release, reuse):
    profile = "release" if release else "debug"
    name = PREFIX + ("reuse" if reuse else "baseline")
    env = clean_env()
    env["VICTORY_DISK_WORKERS"] = "1"
    print(f"profile={profile} mode={'W1' if reuse else 'W0'} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    p = direct([str(exe), "--list", "--ignored"], target, env)
    if p.returncode or any(p.stdout.splitlines().count(PREFIX + mode + ": test") != 1 for mode in ("baseline","reuse")):
        raise ValueError("exact ignored listing")
    p = direct([str(exe), name, "--exact", "--ignored", "--test-threads=1", "--format", "pretty", "--nocapture"], target, env)
    tests = [l for l in p.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in p.stdout.splitlines() if l.startswith("test result:")]
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if p.returncode or tests != [f"test {name} ... ok"] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        raise ValueError("missing exact native test receipt")
    if any(l.startswith("storage_worker_") for l in p.stdout.splitlines()):
        raise ValueError("receipt in stdout")
    return parse_receipts(p.stderr, reuse)

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-storage-worker-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900, env=clean_env())
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        before = inventory(target)
        cmd = [sys.executable, str(ROOT / "tools/prepare_storage_worker_native.py"), str(target)]
        subprocess.run(cmd, check=True, timeout=120, env=clean_env())
        if inventory(target) != before:
            raise ValueError("dry run changed checkout")
        subprocess.run(cmd + ["--apply"], check=True, timeout=120, env=clean_env())
        after = inventory(target)
        if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != {DEST}:
            raise ValueError("unexpected full checkout delta")
        if blob(lf((target/DEST).read_bytes())) != POST:
            raise ValueError("actual postimage identity")
        print(f"inventory_entries={len(before)} changed=1 upstream={UPSTREAM} post={POST}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for release in (False, True):
            exe = build(target, release)
            baseline = run_exact(exe, target, release, False)
            reuse = run_exact(exe, target, release, True)
            if baseline != reuse:
                raise ValueError("packed source length differs between W0/W1")
    print("Four isolated worker correctness receipts only; no timing, cap/default selection, production or FPS proof.")

if __name__ == "__main__":
    main()
