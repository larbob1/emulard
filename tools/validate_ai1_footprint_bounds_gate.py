# SPDX-License-Identifier: GPL-3.0-or-later
"""Native descriptor-only footprint extent receipt; no mapped slices."""
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
RAW = "caf17099100edb798b9eb1913bcc58ffa186201e"
PREPARED = "fe0526831acf2b0f68caa4163fda83b251c22bb0"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
TESTS = ("texture::ai2_footprint_bounds_review::actual_descriptor_final_row_extent",)
FIXTURE = "d5bb76c6f1eec278d3bb99a953bf964670c73b09"
POST = "00cda08ac807cf16ae6a10c8e8f4a12a5fdd3a14"
PATH = "crates/victory-gpu/src/texture.rs"

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
                       errors="replace", timeout=2400)
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

def run_exact(exe, target, release, test):
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith("VICTORY_")}
    env.update(VICTORY_D3D12_WARP="1", VICTORY_LATE_WAIT="0",
               VICTORY_CARD_BUFFERS="0", VICTORY_SWEEP="0")
    # Direct test executable: timeout kills the test process, not just Cargo.
    r = subprocess.run([str(exe), test, "--exact", "--test-threads=1", "--nocapture"],
                       cwd=target, env=env, capture_output=True, text=True,
                       errors="replace", timeout=60)
    # Numeric receipts are emitted on stderr by the exact fixture. Preserve
    # contrary evidence before checking the result.
    print(r.stderr, flush=True)
    labels = ["r8_4x2", "rgba8_aligned", "r8_array_mips", "r8_volume", "bc1_8x8"]
    summary_labels = re.findall(r"^footprint_summary (\S+) total=\d+ full_end=\d+ unpooled_excess=\d+ modeled_pooled_width=\d+$", r.stderr, re.M)
    if summary_labels != labels:
        print(r.stdout, flush=True)
        raise ValueError("missing or unexpected numeric footprint receipts")
    tests = [l for l in r.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in r.stdout.splitlines() if l.startswith("test result:")]
    expected = f"test {test} ... ok"
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if r.returncode or tests != [expected] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        print((r.stderr + "\n" + r.stdout)[-16000:], flush=True)
        raise ValueError("missing exact footprint receipt")
    print(f"{'release' if release else 'debug'} diagnostics {expected}", flush=True)
    print(summaries[0], flush=True)

def main():
    if os.name != "nt":
        raise SystemExit("Windows WARP required")
    if blob(git(ROOT, "show", "HEAD:tools/build_runtime.py")) != BUILDER:
        raise ValueError("builder identity")
    with tempfile.TemporaryDirectory(prefix="ai1-footprint-bounds-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900)
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        path = target / PATH
        original = path.read_bytes()
        prepared = original.replace(b"\r\n", b"\n")
        if blob(git(target, "show", "HEAD:" + PATH)) != RAW or blob(prepared) != PREPARED or b"\r" in prepared:
            raise ValueError("prepared GPU texture identity")
        fixture = (ROOT / "probes/ai2_footprint_bounds.rs").read_bytes().replace(b"\r\n", b"\n")
        if b"ai2_footprint_bounds_review" in prepared or blob(fixture) != FIXTURE:
            raise ValueError("fixture hash mismatch")
        if any(fixture.count(("fn " + t.rsplit("::", 1)[1] + "(").encode()) != 1 for t in TESTS):
            raise ValueError("fixture identity")
        post = prepared + b"\n" + fixture
        if blob(post) != POST:
            raise ValueError("append postimage mismatch")
        path.write_bytes(post.replace(b"\n", b"\r\n") if b"\r\n" in original else post)
        print(f"upstream={UPSTREAM} raw={RAW} prepared={PREPARED} fixture_lf={blob(fixture)} postimage_lf={blob(post)}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for release in (False, True):
            exe = build(target, release)
            for test in TESTS:
                run_exact(exe, target, release, test)
    print("Descriptor-only extent receipt; no allocation/map/slice/queue execution, fix or gameplay evidence.")

if __name__ == "__main__":
    main()
