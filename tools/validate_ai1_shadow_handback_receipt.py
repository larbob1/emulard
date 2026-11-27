# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual owned synchronous shadow handback; no fault injection."""
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
RAW = "458d146aedf6f13dac80782d283a048d80e4a931"
PREPARED = "88acbb3b2cf550cdf2303685fcc32249f9e46328"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
TEST = "host::ai1_shadow_handback_receipt::actual_owned_shadow_handback"
PATH = "crates/victory-gpu/src/host.rs"

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

def run_exact(exe, target, release, wide):
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith("VICTORY_")}
    env.update(VICTORY_D3D12_WARP="1", VICTORY_LATE_WAIT="0",
               VICTORY_CARD_BUFFERS="0", VICTORY_SWEEP="0",
               VICTORY_RELAY="0", VICTORY_WIDE_BACK=str(int(wide)),
               AI1_EXPECT_WIDE=str(int(wide)))
    # Direct test executable: timeout kills the test process, not just Cargo.
    r = subprocess.run([str(exe), TEST, "--exact", "--test-threads=1"],
                       cwd=target, env=env, capture_output=True, text=True,
                       errors="replace", timeout=60)
    tests = [l for l in r.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in r.stdout.splitlines() if l.startswith("test result:")]
    expected = f"test {TEST} ... ok"
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if r.returncode or tests != [expected] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        print((r.stderr + "\n" + r.stdout)[-16000:], flush=True)
        raise ValueError("missing exact shadow handback receipt")
    print(f"{'release' if release else 'debug'} diagnostics wide={int(wide)} {expected}", flush=True)
    print(summaries[0], flush=True)

def main():
    if os.name != "nt":
        raise SystemExit("Windows WARP required")
    if blob(git(ROOT, "show", "HEAD:tools/build_runtime.py")) != BUILDER:
        raise ValueError("builder identity")
    with tempfile.TemporaryDirectory(prefix="ai1-shadow-handback-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900)
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        path = target / PATH
        original = path.read_bytes()
        prepared = original.replace(b"\r\n", b"\n")
        if blob(git(target, "show", "HEAD:" + PATH)) != RAW or blob(prepared) != PREPARED or b"\r" in prepared:
            raise ValueError("prepared host identity")
        shadow = target / 'crates/victory-gpu/src/shadow.rs'
        if blob(shadow.read_bytes().replace(b"\r\n", b"\n")) != '40f1ae02506de251d51e00ebfd36f58e58e7621b':
            raise ValueError('prepared shadow identity')
        fixture = (ROOT / "probes/ai1_shadow_handback_receipt.rs").read_bytes().replace(b"\r\n", b"\n")
        if b"ai1_shadow_handback_receipt" in prepared or fixture.count(b"fn actual_owned_shadow_handback(") != 1:
            raise ValueError("fixture identity")
        post = prepared + b"\n" + fixture
        path.write_bytes(post.replace(b"\n", b"\r\n") if b"\r\n" in original else post)
        print(f"upstream={UPSTREAM} raw={RAW} prepared={PREPARED} fixture_lf={blob(fixture)} postimage_lf={blob(post)}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for release in (False, True):
            exe = build(target, release)
            for wide in (False, True):
                run_exact(exe, target, release, wide)
    print("Small owned positive actual shadow handback only; no parallel cut trigger, card/relay, concurrent writes, failure recovery or gameplay evidence.")

if __name__ == "__main__":
    main()
