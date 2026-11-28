# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated checked texture landing native gate; no production registration."""
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
    args = ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib", "--features",
            "diagnostics", "--no-run", "--message-format=json"]
    if release:
        args.append("--release")
    try:
        r = subprocess.run(args, cwd=target, capture_output=True, text=True,
                           errors="replace", timeout=2400, env=clean_env())
    except subprocess.TimeoutExpired as exc:
        for label, stream in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            print(label + " (partial compile):", flush=True)
            if stream:
                print(stream.decode("utf-8", errors="replace") if isinstance(stream, bytes) else stream, flush=True)
        raise
    if r.returncode:
        print((r.stdout + "\n" + r.stderr)[-20000:], flush=True)
        raise ValueError("test compile failed")
    artifacts = []
    for line in r.stdout.splitlines():
        obj = json.loads(line)
        if (obj.get("reason") == "compiler-artifact" and obj.get("executable")
                and obj.get("target", {}).get("name") == "victory_gpu"
                and obj.get("profile", {}).get("test") is True):
            artifacts.append(Path(obj["executable"]).resolve())
    if len(artifacts) != 1 or not artifacts[0].is_file() or not artifacts[0].is_relative_to(target.resolve()):
        raise ValueError(f"unexpected test executables: {artifacts}")
    return artifacts[0]

REVIEWED = "7a12c705ef903eda1a292ba6fa823063b5b7d4a6"
PREPARER = "tools/prepare_ai2_checked_landing.py"
PINS = {
    PREPARER: "7e68e6a34c2941fe9c6a01d1719d3c56355dfefe",
    "probes/ai2_texback_checked_landing.rs": "a61cd5678cc95b0dc17e6a854f81aa813085d060",
    "probes/ai2_texback_record_resource.rs": "80250d2d44288ba0d708f39c4ed674aec6bc5d30",
    "patches/ai2-checked-landing-common-r2.patch": "57431b71dc138f7f82c82ea97dd60977530ffeda",
    "docs/ai2-texback-checked-landing.md": "43e310668bc6fbed6fc3764b99d3b82ad70a9577",
    "tools/build_runtime.py": BUILDER,
}
POST = {
    "crates/victory-gpu/src/host.rs": "031a65c12bbab967759383b2a75a3be46c46bbde",
    "crates/victory-gpu/src/texback.rs": "eda5777fd077d0492096a6bfe9fadee43d15a2f3",
    "crates/victory-gpu/src/resource.rs": "314c10076c9fa7f07a8fb24f69b4c44f3b758185",
}
CASES = ("Full", "PreserveRefuse", "FinalRefuse", "Prefix")
NAMES = tuple("texback::ai2_checked_landing::actual_checked_" + suffix for suffix in
              ("full", "preserve_refuse", "final_refuse", "prefix"))

def parse_receipts(stdout, stderr, case):
    markers = ("checked_adapter", "checked_case")
    if any(any(k in line for k in markers) for line in stdout.splitlines()):
        raise ValueError("receipt in stdout")
    rows = [line for line in stderr.splitlines() if any(k in line for k in markers)]
    if len(rows) != 2:
        raise ValueError("missing, duplicate or displaced checked receipts")
    signed = r"(0|-?[1-9][0-9]*)"
    unsigned = r"(0|[1-9][0-9]*)"
    m = re.fullmatch("checked_adapter actual_high=" + signed + " actual_low=" + unsigned
                     + " warp_high=" + signed + " warp_low=" + unsigned + " software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")
    preserve, transfer, published, outcome = (
        (2560, 2560, 48, "Complete"),
        (0, 0, 0, "NotAttempted"),
        (2560, 0, 0, "NotAttempted"),
        (2560, 1027, 20, "Incomplete"),
    )[case]
    p, t = int(preserve != 0), int(transfer != 0)
    prefix = (
        f"checked_case mode={CASES[case]} selected=1 recorded=1 submitted=1 fence=1 healthy=1 "
        f"obligation=2560 preserve_attempted={p} preserve_requested={preserve} preserve_success={p} preserve_done={preserve} "
        f"tiles={4*p} mapped={p} unmapped={p} transfer_attempted={t} transfer_requested={transfer} "
        f"transfer_success={t} transfer_done={transfer} outcome={outcome} gpu_active=48 published_active={published} "
        "preserved=2512 guards=62976 cleanup=1"
    )
    m = re.fullmatch(prefix + " extent=" + unsigned + " width=" + unsigned + " classifier=10", rows[1])
    if not m:
        raise ValueError("malformed checked landing receipt")
    extent, width = map(int, m.groups())
    if not 0 < extent <= 65536 or not extent <= width < 2**64:
        raise ValueError("readback extent/width")
    return ah, al, extent, width

def lf(data):
    return data.replace(b"\r\n", b"\n")

def clean_env():
    return {k:v for k,v in os.environ.items()
            if not k.upper().startswith(("VICTORY_", "RUST_TEST_", "AI2_", "AI5_", "AI6_"))
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

def verify_case(stdout, stderr, code, case, total):
    if case not in range(len(CASES)) or total < len(CASES):
        raise ValueError("unsupported case or discovery")
    out = stdout.splitlines()
    err = stderr.splitlines()
    if any(re.search(r"\bpanicked at\b|\bthread .* panicked\b", l, re.IGNORECASE) for l in out + err):
        raise ValueError("unexpected panic")
    def framing(line):
        return ("test result:" in line
                or re.search(r"\btest\s+\S+\s+\.\.\.", line)
                or re.match(r"^\s*test\s", line)
                or re.search(r"\brunning\s+\d+\s+tests?\b", line))
    if any(framing(l) for l in err):
        raise ValueError("unexpected libtest framing in stderr")
    frames = [l for l in out if framing(l)]
    name_line = f"test {NAMES[case]} ... ok"
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; " + str(total - 1) + r" filtered out; finished in [0-9]+(?:\.[0-9]+)?s"
    if (code != 0 or len(frames) != 3
            or frames[:2] != ["running 1 test", name_line]
            or not re.fullmatch(summary, frames[2])):
        raise ValueError("missing exact normal receipt")
    return parse_receipts(stdout, stderr, case)

def run_exact(exe, target, release, case):
    profile = "release" if release else "debug"
    env = clean_env()
    flags = {"VICTORY_D3D12_WARP": "1", "VICTORY_SWEEP": "0", "VICTORY_TEXTURE_BACK": "7x3f61"}
    env.update(flags)
    print(f"profile={profile} case={CASES[case]} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(flags, sort_keys=True) + " VICTORY_COPY_MODE=absent VICTORY_COPY_ASK=absent", flush=True)
    def discover(ignored):
        args = [str(exe), "--list"] + (["--ignored"] if ignored else [])
        p = direct(args, target, env)
        if p.returncode or any(re.search(
                r"\b\S+: (?:test|benchmark)\b|\b\d+ tests?, \d+ benchmarks?\b|\bpanicked at\b",
                line, re.IGNORECASE) for line in p.stderr.splitlines()):
            raise ValueError("discovery exit or contradictory stderr")
        lines = [l for l in p.stdout.splitlines() if l]
        if not lines:
            raise ValueError("empty discovery")
        m = re.fullmatch(r"(0|[1-9][0-9]*) tests?, (0|[1-9][0-9]*) benchmarks?", lines[-1])
        if not m or int(m[2]) != 0:
            raise ValueError("unexpected discovery summary")
        tests = lines[:-1]
        if len(tests) != int(m[1]) or len(set(tests)) != len(tests) or any(not re.fullmatch(r"\S+: test", l) for l in tests):
            raise ValueError("inconsistent discovery inventory")
        if any(tests.count(n + ": test") != 1 for n in NAMES):
            raise ValueError("missing exact case")
        return set(tests)
    full = discover(False)
    ignored = discover(True)
    if not ignored <= full:
        raise ValueError("ignored discovery not subset of full")
    print(f"discovered_total={len(full)} ignored_total={len(ignored)}", flush=True)
    p = direct([str(exe), NAMES[case], "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"], target, env)
    print(f"child_exit case={CASES[case]} code={p.returncode}", flush=True)
    receipt = verify_case(p.stdout, p.stderr, p.returncode, case, len(full))
    print(f"accepted case={CASES[case]} exit={p.returncode} kind=normal", flush=True)
    return full, ignored, receipt

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-checked-landing-") as tmp:
        owned = Path(tmp).absolute()
        if owned.is_symlink() or owned.is_junction() or not owned.is_dir():
            raise ValueError("unexpected temporary root type")
        canonical = owned.resolve(strict=True)
        if not owned.samefile(canonical) or canonical == ROOT or ROOT in canonical.parents or canonical in ROOT.parents:
            raise ValueError("temporary root identity or overlap")
        target = canonical / "runtime"
        if target.exists() or target.is_symlink() or target.is_junction():
            raise ValueError("runtime child must be absent")
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900, env=clean_env())
        if (target.is_symlink() or target.is_junction() or not target.is_dir()
                or target.resolve(strict=True) != target or not owned.samefile(canonical)
                or not target.parent.samefile(canonical)):
            raise ValueError("runtime child identity")
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        before = inventory(target)
        cmd = [sys.executable, str(ROOT / PREPARER), str(target)]
        subprocess.run(cmd, check=True, timeout=120, env=clean_env())
        if inventory(target) != before:
            raise ValueError("dry run changed checkout")
        subprocess.run(cmd + ["--apply"], check=True, timeout=120, env=clean_env())
        after = inventory(target)
        if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != set(POST):
            raise ValueError("unexpected full checkout delta")
        for path, expected in POST.items():
            if blob(lf((target/path).read_bytes())) != expected:
                raise ValueError("actual postimage identity: " + path)
        print(f"inventory_entries={len(before)} changed=3 upstream={UPSTREAM}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        digests = set()
        baseline = None
        for release in (False, True):
            exe = build(target, release)
            digest = hashlib.sha256(exe.read_bytes()).hexdigest()
            if digest in digests:
                raise ValueError("debug and release executable identities must differ")
            digests.add(digest)
            for case in range(len(CASES)):
                if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
                    raise ValueError("profile executable changed before case")
                observed = run_exact(exe, target, release, case)
                if baseline is None:
                    baseline = observed
                elif observed != baseline:
                    raise ValueError("discovery changed across cases")
                if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
                    raise ValueError("profile executable changed after case")
    print("Eight exact checked texture landing normal cases passed; no production or gameplay proof.")

if __name__ == "__main__":
    main()
