# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated actual storage file metadata lifetime gate."""
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
                and obj.get("target", {}).get("name") == "victory_hle"
                and obj.get("profile", {}).get("test") is True):
            artifacts.append(Path(obj["executable"]).resolve())
    if len(artifacts) != 1 or not artifacts[0].is_file() or not artifacts[0].is_relative_to(target.resolve()):
        raise ValueError(f"unexpected test executables: {artifacts}")
    return artifacts[0]

REVIEWED = "eea95f8cf57312ed732c5d16d24e4bd8d2c7943a"
PINS = {
    "tools/prepare_storage_file_lifetime_native.py": "de79c7b40c0838f5ee170efdeb534befd6b99918",
    "probes/storage_file_lifetime_native.rs": "3860879590b6123c2609b6059a03d1ff7a40ae3d",
    "docs/storage-file-lifetime-native.md": "4e998f6e5ab8f32711a5f7834fb48d018a5f2b5c",
    "tools/build_runtime.py": BUILDER,
}
POST = {"crates/victory-hle/src/modules/dstorage.rs": "e30f2a01f84ac9bb0e37e7a3415a3902ce12f726"}
MANIFESTS = {
    "crates/victory-hle/Cargo.toml": "a2fa943c5095cfd8256ee3e9a7c5d2a51cde6ac7",
    "Cargo.toml": "4e21b692d66103d990003164b6f1e4f700bc4086",
    "Cargo.lock": "29bab8c72233fbd9552e646c79316bc9439df0d7",
}
CASES = ("B0", "B1")
NAMES = (
    "modules::dstorage::tests::storage_file_lifetime_baseline",
    "modules::dstorage::tests::storage_file_lifetime_candidate",
)
RECEIPTS = (
    "storage_file_lifetime mode=0 a2=2 a1=1 a0=0 b2=2 b1=1 b0=0 open=2 nonlast=2 after_a=2 after_b=2 other=1 prefree1=0 prefree2=0 prefree3=0",
    "storage_file_lifetime mode=1 a2=2 a1=1 a0=0 b2=2 b1=1 b0=0 open=2 nonlast=2 after_a=1 after_b=0 other=1 prefree1=0 prefree2=1 prefree3=2",
)

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
    if any("storage_file_lifetime" in l and l != name_line for l in out):
        raise ValueError("receipt or unexpected name in stdout")
    rows = [l for l in err if "storage_file_lifetime" in l]
    if rows != [RECEIPTS[case]]:
        raise ValueError("missing, duplicate, displaced or incorrect receipt")

def run_exact(exe, target, release, case):
    profile = "release" if release else "debug"
    env = clean_env()
    print(f"profile={profile} case={CASES[case]} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=all inherited VICTORY_ flags absent", flush=True)
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
    verify_case(p.stdout, p.stderr, p.returncode, case, len(full))
    print(f"accepted case={CASES[case]} exit={p.returncode} kind=normal", flush=True)
    return full, ignored

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-storage-file-lifetime-") as tmp:
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
        for path, expected in MANIFESTS.items():
            if blob(git(target, "show", f"HEAD:{path}")) != expected or blob(lf((target/path).read_bytes())) != expected:
                raise ValueError("raw/prepared manifest identity: " + path)
            print(f"manifest={path} raw={expected} prepared={expected}", flush=True)
        cmd = [sys.executable, str(ROOT / "tools/prepare_storage_file_lifetime_native.py"), str(target)]
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
        print(f"inventory_entries={len(before)} changed=1 upstream={UPSTREAM}", flush=True)
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
    print("Four exact storage file lifetime normal cases passed.")

if __name__ == "__main__":
    main()
