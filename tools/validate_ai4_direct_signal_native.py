# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated direct guest signal witness."""
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

REVIEWED = "6977bbaa0b27a6923ee5aeeb991a1eeaf67f9d3b"
PINS = {
    "tools/prepare_ai6_direct_signal_witness.py": "7752275a58421c31c6e7a40b8d2aea290a5a624e",
    "probes/ai6_direct_signal_witness.rs": "a3c4a0c4d51c24b0c723177d4bc83958962b843a",
    "probes/ai6_direct_signal_witness_host.rs": "d023a00f3627b4652b5e85128ec527d1129b9391",
    "docs/ai6-direct-signal-witness.md": "404c195ac9f3960e06ee95bb6187509c36872917",
    "tools/build_runtime.py": BUILDER,
}
POST = {
    "crates/victory-gpu/src/queue.rs": "a00dd7fb283b4c13de6f0dae781130331e5d9434",
    "crates/victory-gpu/src/host.rs": "75b8d658d9bff531150f0e0d49ec457a8c916efd",
}
MANIFESTS = {
    "crates/victory-gpu/Cargo.toml": "e6d844522016d5bb476dc04ad972b0e0498d7c86",
    "Cargo.toml": "4e21b692d66103d990003164b6f1e4f700bc4086",
    "Cargo.lock": "29bab8c72233fbd9552e646c79316bc9439df0d7",
}
CASES = ('D0', 'D1', 'I0')
NAMES = (
    'queue::ai6_direct_signal_witness::actual_direct_signal_d0',
    'queue::ai6_direct_signal_witness::actual_direct_signal_d1',
    'queue::ai6_direct_signal_witness::actual_direct_signal_i0',
)
RECEIPTS = (
    'direct_signal_case id=D0 submissions=1 selected=1 refused=0 healthy_fences=1 producer_bytes=64 guard_bytes=24 marker_writes=0 guest_before=0 guest_after=17 signal_ok=1 held=0 waiting=0 cleanup=1',
    'direct_signal_case id=D1 submissions=1 selected=1 refused=1 healthy_fences=1 producer_bytes=0 sentinel_bytes=88 guard_bytes=24 marker_writes=0 guest_before=0 guest_after=17 signal_ok=1 held=0 waiting=0 cleanup=0 terminal=87',
    'direct_signal_case id=I0 submissions=0 selected=0 refused=0 guest_before=0 guest_after=17 signal_ok=1 held=0 waiting=0 cleanup=1',
)
FLAGS = {"VICTORY_" + k: v for k, v in {
    "D3D12_WARP":"1", "QUEUE_WAIT":"1", "SPLIT_WAITS":"0", "CUT_WAITS":"0",
    "WAIT_FORCE":"0", "WAIT_ASK":"0", "LATE_WAIT":"0", "ASYNC_SUBMIT":"0",
    "JOIN_PARTS":"0", "ASYNC_PRESENT":"0", "CARD_BUFFERS":"0", "RELAY":"0",
    "WIDE_BACK":"0",
}.items()}
def lf(data):
    return data.replace(b"\r\n", b"\n")

def clean_env():
    return {k:v for k,v in os.environ.items()
            if not k.upper().startswith(("VICTORY_", "RUST_TEST_", "AI6_"))
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
    if case not in range(len(CASES)):
        raise ValueError("unsupported case")
    out = stdout.splitlines()
    err = stderr.splitlines()
    all_lines = out + err
    if any(re.search(r"\bpanicked at\b|\bthread .* panicked\b", l, re.IGNORECASE) for l in all_lines):
        raise ValueError("unexpected panic")
    # Reject displaced or contradictory framing in either stream. Only
    # canonical stdout lines, in order, can attest a libtest invocation.
    def framing(line):
        return ("test result:" in line
                or re.search(r"\btest\s+\S+\s+\.\.\.", line)
                or re.match(r"^\s*test\s", line)
                or re.search(r"\brunning\s+\d+\s+tests?\b", line))
    if any(framing(l) for l in err):
        raise ValueError("unexpected libtest framing in stderr")
    frames = [l for l in out if framing(l)]
    if case != 1:
        summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; " + str(total - 1) + r" filtered out; finished in [0-9]+(?:\.[0-9]+)?s"
        if (code != 0 or len(frames) != 3
                or frames[:2] != ["running 1 test", f"test {NAMES[case]} ... ok"]
                or not re.fullmatch(summary, frames[2])):
            raise ValueError("missing exact normal receipt")
    else:
        # A direct exit may omit the partially flushed test name.
        if code != 87 or frames not in (["running 1 test"],
                ["running 1 test", f"test {NAMES[case]} ... "],
                ["running 1 test", f"test {NAMES[case]} ..."]):
            raise ValueError("D1 must be a dedicated witness exit, not a libtest result")
    if any("direct_signal_adapter" in l or "direct_signal_case" in l for l in stdout.splitlines()):
        raise ValueError("receipt in stdout")
    rows = [l for l in stderr.splitlines() if "direct_signal_adapter" in l or "direct_signal_case" in l]
    if len(rows) != 2 or rows[1] != RECEIPTS[case]:
        raise ValueError("missing, extra, displaced or reordered receipt")
    signed = r"(0|-?[1-9][0-9]*)"
    unsigned = r"(0|[1-9][0-9]*)"
    m = re.fullmatch("direct_signal_adapter actual_high=" + signed + " actual_low=" + unsigned
                     + " warp_high=" + signed + " warp_low=" + unsigned + " software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")
    return ah, al

def run_exact(exe, target, release, case):
    profile = "release" if release else "debug"
    env = clean_env()
    env.update(FLAGS)
    print(f"profile={profile} case={CASES[case]} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(FLAGS, sort_keys=True), flush=True)
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
    adapter = verify_case(p.stdout, p.stderr, p.returncode, case, len(full))
    print(f"accepted case={CASES[case]} exit={p.returncode} kind={'witness' if case == 1 else 'normal'}", flush=True)
    return adapter, full, ignored

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai4-direct-signal-") as tmp:
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
        cmd = [sys.executable, str(ROOT / "tools/prepare_ai6_direct_signal_witness.py"), str(target)]
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
        print(f"inventory_entries={len(before)} changed=2 upstream={UPSTREAM}", flush=True)
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
                    raise ValueError("adapter or discovery changed across cases")
                if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
                    raise ValueError("profile executable changed after case")
    print("Four normal controls and two dedicated D1 adverse witnesses.")

if __name__ == "__main__":
    main()
