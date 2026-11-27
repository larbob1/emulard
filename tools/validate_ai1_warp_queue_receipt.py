# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent WARP queue primitive receipt; not Host::submit or gameplay."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
RAW = "458d146aedf6f13dac80782d283a048d80e4a931"
PREPARED = "88acbb3b2cf550cdf2303685fcc32249f9e46328"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
TEST = "host::ai1_warp_queue_receipt::actual_owned_queue_receipt"
PATH = "crates/victory-gpu/src/host.rs"

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)

def run_exact(target, release):
    args = ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib", "--features", "diagnostics"]
    if release:
        args.append("--release")
    args.extend([TEST, "--", "--exact", "--test-threads=1"])
    env = dict(os.environ, VICTORY_D3D12_WARP="1")
    r = subprocess.run(args, cwd=target, env=env, capture_output=True, text=True,
                       errors="replace", timeout=3600)
    tests = [l for l in r.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in r.stdout.splitlines() if l.startswith("test result:")]
    expected = f"test {TEST} ... ok"
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if r.returncode or tests != [expected] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        print((r.stderr + "\n" + r.stdout)[-16000:], flush=True)
        raise ValueError("missing exact independent queue receipt")
    print(("release" if release else "debug") + " diagnostics " + expected, flush=True)
    print(summaries[0], flush=True)

def main():
    if os.name != "nt":
        raise SystemExit("Windows WARP required")
    if blob(git(ROOT, "show", "HEAD:tools/build_runtime.py")) != BUILDER:
        raise ValueError("builder identity")
    with tempfile.TemporaryDirectory(prefix="ai1-warp-queue-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900)
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        raw = git(target, "show", "HEAD:" + PATH)
        path = target / PATH
        original = path.read_bytes()
        prepared = original.replace(b"\r\n", b"\n")
        if blob(raw) != RAW or blob(prepared) != PREPARED or b"\r" in prepared:
            raise ValueError("prepared host identity")
        fixture = (ROOT / "probes/ai1_warp_queue_receipt.rs").read_bytes().replace(b"\r\n", b"\n")
        if b"ai1_warp_queue_receipt" in prepared or fixture.count(b"fn actual_owned_queue_receipt(") != 1:
            raise ValueError("fixture identity")
        post = prepared + b"\n" + fixture
        path.write_bytes(post.replace(b"\n", b"\r\n") if b"\r\n" in original else post)
        print(f"upstream={UPSTREAM} raw={RAW} prepared={PREPARED} fixture_lf={blob(fixture)} postimage_lf={blob(post)}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        run_exact(target, False)
        run_exact(target, True)
    print("Independent owned queue primitives only; not Host::submit, publication, copyback or gameplay.")

if __name__ == "__main__":
    main()
