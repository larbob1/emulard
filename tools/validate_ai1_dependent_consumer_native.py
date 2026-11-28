# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated positive whole-wait native gate; no production registration."""
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

REVIEWED = "49c86e9f9c51c754c3dd143c56aa91bc67e383b1"
PINS = {
    "tools/prepare_ai6_dependent_consumer.py": "98959fcf8dba362159d42f25a995ebd4ca6e20ff",
    "probes/ai6_dependent_consumer.rs": "755602d634e6e6c083c7f88611a17a44306cbc76",
    "probes/ai6_dependent_consumer_host.rs": "5b218179ed67ac6df956840adbc139021a8bc7de",
    "docs/ai6-dependent-consumer.md": "b927b5aa2c42d6bfc79cdce25ffde6af5e2ad08d",
    "tools/build_runtime.py": BUILDER,
}
POST = {
    "crates/victory-gpu/src/queue.rs": "a32db134dc909c2bde7bddb6fee87d63cbf8fdd7",
    "crates/victory-gpu/src/host.rs": "0bd298de41f2db3f196d64bddffb1555d93ce226",
}
NAME = "queue::ai6_dependent_consumer::actual_whole_wait_dependent_consumer"
FLAGS = {"VICTORY_" + k: v for k, v in {
    "D3D12_WARP":"1", "QUEUE_WAIT":"1", "SPLIT_WAITS":"0", "CUT_WAITS":"0",
    "WAIT_FORCE":"0", "WAIT_ASK":"0", "LATE_WAIT":"0", "ASYNC_SUBMIT":"0",
    "JOIN_PARTS":"0", "ASYNC_PRESENT":"0", "CARD_BUFFERS":"0", "RELAY":"0",
    "WIDE_BACK":"0",
}.items()}
RECEIPT = ("dependent_consumer held=3 detached=1 order=0 healthy_fences=2 "
           "producer_bytes=64 consumer_bytes=64 guard_bytes=48 marker=wide_equal "
           "guest_fence=17 forced=0 residue=0 events=0,1,2,3,4,5,6,7")

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

def run_exact(exe, target, release):
    profile = "release" if release else "debug"
    env = clean_env()
    env.update(FLAGS)
    print(f"profile={profile} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(FLAGS, sort_keys=True), flush=True)
    p = direct([str(exe), "--list", "--ignored"], target, env)
    if p.returncode or p.stdout.splitlines().count(NAME + ": test") != 1:
        raise ValueError("exact ignored listing")
    p = direct([str(exe), NAME, "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"], target, env)
    tests = [l for l in p.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in p.stdout.splitlines() if l.startswith("test result:")]
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if p.returncode or tests != [f"test {NAME} ... ok"] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        raise ValueError("missing exact native test receipt")
    rows = [l for l in p.stderr.splitlines() if l.startswith(("dependent_adapter", "dependent_consumer"))]
    if len(rows) != 2 or rows[1] != RECEIPT:
        raise ValueError("missing, extra or reordered dependent receipt")
    m = re.fullmatch(r"dependent_adapter actual_high=(-?\d+) actual_low=(\d+) warp_high=(-?\d+) warp_low=(\d+) software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-dependent-consumer-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900, env=clean_env())
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        before = inventory(target)
        cmd = [sys.executable, str(ROOT / "tools/prepare_ai6_dependent_consumer.py"), str(target)]
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
            run_exact(build(target, release), target, release)
    print("Two isolated positive legacy whole-wait receipts only; no production failure, gameplay or FPS proof.")

if __name__ == "__main__":
    main()
