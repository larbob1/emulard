# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated texture landing native gate; no production registration."""
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
    r = subprocess.run(args, cwd=target, capture_output=True, text=True,
                       errors="replace", timeout=2400, env=clean_env())
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

REVIEWED = "5412e4229dce792e7e840c3f33612148faeea0ae"
PREPARER = "tools/prepare_ai2_landing_boundary.py"
PINS = {
    "probes/ai2_texback_record_resource.rs": "80250d2d44288ba0d708f39c4ed674aec6bc5d30",
    "probes/ai2_texback_landing_boundary.rs": "c90bea37779ff6422a377b96999974bd614ad21e",
    "docs/ai2-texback-landing-boundary.md": "4bdc6ae1ea017e94eb2733c01ffc36d41bb47e70",
    PREPARER: "6c2e929e83407972de0c875833a7966e883a31f0",
    "tools/build_runtime.py": BUILDER,
}
NAMES = ("texback::ai2_landing_boundary::actual_landing_control",
         "texback::ai2_landing_boundary::actual_landing_refusal")
POST = {
    "crates/victory-gpu/src/texback.rs": "3b6f4b9cfba18f7908a836d3b31d4e82c31d230d",
    "crates/victory-gpu/src/resource.rs": "314c10076c9fa7f07a8fb24f69b4c44f3b758185",
}
def lf(data):
    return data.replace(b"\r\n", b"\n")

def clean_env():
    return {k:v for k,v in os.environ.items()
            if not k.upper().startswith(("VICTORY_", "RUST_TEST_", "AI2_", "AI6_"))
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


def parse_receipts(stdout, stderr, case):
    if any("landing_adapter" in l or "landing_case" in l for l in stdout.splitlines()):
        raise ValueError("receipt in stdout")
    rows = [l for l in stderr.splitlines() if "landing_adapter" in l or "landing_case" in l]
    if len(rows) != 2:
        raise ValueError("missing, extra or displaced receipts")
    signed = r"(0|-?[1-9][0-9]*)"
    unsigned = r"(0|[1-9][0-9]*)"
    m = re.fullmatch("landing_adapter actual_high=" + signed + " actual_low=" + unsigned
                     + " warp_high=" + signed + " warp_low=" + unsigned + " software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")
    mode, published = ("control", 48) if case == 0 else ("refusal", 0)
    prefix = (f"landing_case mode={mode} selected=1 recorded=1 submitted=1 fence=1 healthy=1 hits=1 "
              f"staged=2560 staged_active=48 active_declared=48 gpu_active=48 published_active={published} "
              "preserved=2512 guards=62976 cleanup=1")
    m = re.fullmatch(prefix + " extent=" + unsigned + " width=" + unsigned, rows[1])
    if not m:
        raise ValueError("malformed landing receipt")
    extent, width = map(int, m.groups())
    if not 0 < extent <= 65536 or not extent <= width < 2**64:
        raise ValueError("readback extent/width")
    return (ah, al, extent, width)

def run_exact(exe, target, release, case):
    profile = "release" if release else "debug"
    name = NAMES[case]
    env = clean_env()
    flags = {"VICTORY_D3D12_WARP": "1", "VICTORY_SWEEP": "0", "VICTORY_TEXTURE_BACK": "7x3f61"}
    env.update(flags)
    print(f"profile={profile} case=R{case} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(flags, sort_keys=True) + " VICTORY_COPY_MODE=absent VICTORY_COPY_ASK=absent", flush=True)
    p = direct([str(exe), "--list", "--ignored"], target, env)
    if p.returncode or any(p.stdout.splitlines().count(n + ": test") != 1 for n in NAMES):
        raise ValueError("exact ignored listing")
    p = direct([str(exe), name, "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"], target, env)
    tests = [l for l in p.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in p.stdout.splitlines() if l.startswith("test result:")]
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if p.returncode or tests != [f"test {name} ... ok"] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        raise ValueError("missing exact native test receipt")
    return parse_receipts(p.stdout, p.stderr, case)

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-texback-landing-") as tmp:
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
        command = [sys.executable, str(ROOT / PREPARER), str(target)]
        subprocess.run(command, check=True, timeout=120, env=clean_env())
        if inventory(target) != before:
            raise ValueError("dry-run altered checkout")
        subprocess.run(command + ["--apply"], check=True, timeout=120, env=clean_env())
        after = inventory(target)
        if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != set(POST):
            raise ValueError("unexpected full checkout delta")
        for path, expected in POST.items():
            if blob(lf((target/path).read_bytes())) != expected:
                raise ValueError("actual postimage identity: " + path)
        print(f"inventory_entries={len(before)} changed=2 upstream={UPSTREAM}", flush=True)
        receipts = []
        digests = []
        for release in (False, True):
            exe = build(target, release)
            digest = hashlib.sha256(exe.read_bytes()).hexdigest()
            digests.append(digest)
            for case in (0, 1):
                receipts.append(run_exact(exe, target, release, case))
                if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
                    raise ValueError("test binary changed")
        if len(set(receipts)) != 1 or len(set(digests)) != 2:
            raise ValueError("adapter/footprint parity or profile executable identity")
    print("Four isolated texture landing receipts only; no driver failure, notification, production policy, gameplay or FPS proof.")

if __name__ == "__main__":
    main()
