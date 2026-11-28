# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated B0/B1 readback publication witness; no production registration."""
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

REVIEWED = "696c4cd695de5bf1c8072b802156d4d4a239ea04"
PINS = {
    "tools/prepare_ai6_readback_witness.py": "10d4a09c07a0dd0fa8a311885a37c4f2dd06e091",
    "probes/ai6_readback_witness.rs": "5d788f3c00eb4a993cbfb0bd88961c43d9376867",
    "probes/ai6_readback_witness_host.rs": "7c76e807a58d1eb972b1d7bedc515f1361fa812d",
    "docs/ai6-readback-witness.md": "cb65fe701e1cfee97893ece4b666241bb09c61ff",
    "tools/build_runtime.py": BUILDER,
}
POST = {
    "crates/victory-gpu/src/queue.rs": "cabd9188b2fe7b656612a7a5910b73e4ec707875",
    "crates/victory-gpu/src/host.rs": "84fb1319bf8c0c97d88b55a397a98d19bdbfc0f3",
}
MANIFESTS = {
    "crates/victory-gpu/Cargo.toml": "e6d844522016d5bb476dc04ad972b0e0498d7c86",
    "Cargo.toml": "4e21b692d66103d990003164b6f1e4f700bc4086",
    "Cargo.lock": "29bab8c72233fbd9552e646c79316bc9439df0d7",
}
NAMES = ("queue::ai6_readback_witness::actual_readback_b0",
         "queue::ai6_readback_witness::actual_readback_b1")
RECEIPTS = (
    "readback_case id=0 selected=1 refused=0 published=1 stopped=0 healthy_fences=2 producer_bytes=64 consumer_bytes=64 guard_bytes=48 marker=wide_equal guest_fence=17 held=0 waiting=0 forced=0 retired=0 events=0,1,2,3,4,5,6,7",
    "readback_case id=1 selected=1 refused=1 published=1 stopped=1 healthy_fences=1 producer_bytes=0 consumer_bytes=0 sentinel_bytes=176 guard_bytes=48 marker=wide_equal guest_fence=0 held=3 waiting=1 forced=0 retired=0 terminal=86",
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

def verify_case(stdout, stderr, code, case):
    if case not in (0, 1):
        raise ValueError("unsupported case")
    names = [l for l in stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in stdout.splitlines() if l.startswith("test result:")]
    if case == 0:
        summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; [0-9]+ filtered out; finished in [0-9]+(?:\.[0-9]+)?s"
        if code != 0 or names != [f"test {NAMES[0]} ... ok"] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
            raise ValueError("missing exact B0 normal receipt")
    else:
        # libtest may print the test prefix before the process exits.
        if code != 86 or summaries or any(l.strip() != f"test {NAMES[1]} ..." for l in names):
            raise ValueError("B1 must be a dedicated witness exit, not a libtest result")
        if "test result:" in stderr or any(re.search(r"\b(?:panicked at|thread .* panicked)\b", l) for l in stderr.splitlines()):
            raise ValueError("B1 unexpected panic or test summary")
    if any("readback_adapter" in l or "readback_case" in l for l in stdout.splitlines()):
        raise ValueError("receipt in stdout")
    rows = [l for l in stderr.splitlines() if "readback_adapter" in l or "readback_case" in l]
    if len(rows) != 2 or rows[1] != RECEIPTS[case]:
        raise ValueError("missing, extra, displaced or reordered receipt")
    signed = r"(0|-?[1-9][0-9]*)"
    unsigned = r"(0|[1-9][0-9]*)"
    m = re.fullmatch("readback_adapter actual_high=" + signed + " actual_low=" + unsigned
                     + " warp_high=" + signed + " warp_low=" + unsigned + " software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")

def run_exact(exe, target, release, case):
    profile = "release" if release else "debug"
    env = clean_env()
    env.update(FLAGS)
    print(f"profile={profile} case=B{case} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(FLAGS, sort_keys=True), flush=True)
    p = direct([str(exe), "--list", "--ignored"], target, env)
    if p.returncode or any(p.stdout.splitlines().count(n + ": test") != 1 for n in NAMES):
        raise ValueError("exact ignored listing")
    p = direct([str(exe), NAMES[case], "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"], target, env)
    verify_case(p.stdout, p.stderr, p.returncode, case)
    print(f"accepted case=B{case} exit={p.returncode} kind={'normal' if case == 0 else 'witness'}", flush=True)

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-readback-witness-") as tmp:
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
        cmd = [sys.executable, str(ROOT / "tools/prepare_ai6_readback_witness.py"), str(target)]
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
        for release in (False, True):
            exe = build(target, release)
            for case in (0, 1):
                run_exact(exe, target, release, case)
    print("Two B0 normal passes and two B1 dedicated adverse witnesses; no production failure fix, gameplay or FPS proof.")

if __name__ == "__main__":
    main()
