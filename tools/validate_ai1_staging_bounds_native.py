# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated exact AI2 staging allocation preview; not production registration."""
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
TEST = "texture::ai2_staging_bounds_allocation::"
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

from preview_ai2_staging_bounds import transform

FIXTURE = "061e6a579d5dd071279de7601ce3d7271e19a918"
PREVIEW = "ebdd3e1148522d2a1e0ba31fdc23fa79441b4d4b"
CANDIDATE = "30d690616b8e215e3019e2c41d12287e247f92ad"
POST = "d86558c0e2ed3c21c4454c56d75a61eacb6232e0"

def run_exact(exe, target, release, descriptor, pool):
    env = {k:v for k,v in os.environ.items()
           if not k.upper().startswith(("VICTORY_", "AI2_"))}
    env.update(VICTORY_D3D12_WARP="1", VICTORY_SWEEP="0",
               VICTORY_COMMITTED_QUERY="1", VICTORY_STAGING_POOL=str(pool),
               AI2_EXPECT_POOL=str(pool), RUST_TEST_NOCAPTURE="1")
    name = TEST + ("actual_staging_extent_descriptor_compatibility" if descriptor
                   else "actual_staging_bounds_pool_and_zero_fill")
    print(f"profile={'release' if release else 'debug'} pool={pool} filter={name}", flush=True)
    r = subprocess.run([str(exe), name, "--exact", "--test-threads=1", "--nocapture"],
                       cwd=target, env=env, capture_output=True, text=True,
                       errors="replace", timeout=60)
    print(r.stdout, flush=True)
    print(r.stderr, flush=True)
    tests = re.findall(r"^test (\S+) \.\.\. ok\s*$", r.stdout, re.M)
    summaries = [l for l in r.stdout.splitlines() if l.startswith("test result:")]
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if r.returncode or tests != [name] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        raise ValueError("missing exact staging test receipt")
    adapters = re.findall(r"^staging_adapter actual_high=(-?\d+) actual_low=(\d+) warp_high=(-?\d+) warp_low=(\d+) software=1\s*$", r.stderr, re.M)
    if len(adapters) != 1 or adapters[0][:2] != adapters[0][2:]:
        raise ValueError("actual device identity receipt")
    if descriptor:
        expected = [(260,512),(512,512),(3586,3840),(2824,3072),(272,512)]
        got = [(int(a),int(b)) for a,b in re.findall(r"^staging_extent .+ total=(\d+) full=(\d+)\s*$",r.stderr,re.M)]
        if got != expected:
            raise ValueError("descriptor receipts")
    else:
        small = re.findall(r"^staging_bounds small pool=(\d+) logical=(\d+) required=(\d+) width=(\d+) reused=(true|false)\s*$",r.stderr,re.M)
        want = (str(pool),"260","512",str(65536 if pool else 512),str(bool(pool)).lower())
        if small != [want]:
            raise ValueError("small allocation receipt")
        got = [tuple(map(int,x)) for x in re.findall(r"^staging_bounds boundary pool=(\d+) logical=(\d+) required=(\d+) width=(\d+) class=(\d+)\s*$",r.stderr,re.M)]
        sizes = (65536,8388608,8389632)
        expected = [(pool, 256*255+4, sizes[0], sizes[0], sizes[0] if pool else 0),
                    (pool,1024*8191+1001,sizes[1],sizes[1],sizes[1] if pool else 0),
                    (pool,1024*8192+1001,sizes[2],sizes[2],0)]
        if got != expected:
            raise ValueError("boundary allocation receipts")

def main():
    if os.name != "nt":
        raise SystemExit("Windows WARP required")
    for path, pin in [("tools/build_runtime.py", BUILDER),
                      ("tools/preview_ai2_staging_bounds.py", PREVIEW),
                      ("probes/ai2_staging_bounds_allocation.rs", FIXTURE)]:
        if blob(git(ROOT, "show", "HEAD:" + path)) != pin:
            raise ValueError("repository identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-staging-bounds-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900)
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        path = target / PATH
        original = path.read_bytes()
        prepared = original.replace(b"\r\n", b"\n")
        if blob(git(target, "show", "HEAD:" + PATH)) != RAW or blob(prepared) != PREPARED:
            raise ValueError("prepared texture identity")
        candidate = transform(prepared)
        fixture = (ROOT / "probes/ai2_staging_bounds_allocation.rs").read_bytes().replace(b"\r\n", b"\n")
        post = candidate + b"\n" + fixture
        if (blob(candidate), blob(fixture), blob(post)) != (CANDIDATE, FIXTURE, POST):
            raise ValueError("exact candidate/fixture/postimage identity")
        path.write_bytes(post.replace(b"\n", b"\r\n") if b"\r\n" in original else post)
        if path.read_bytes().replace(b"\r\n",b"\n") != post:
            raise ValueError("written postimage")
        print(f"upstream={UPSTREAM} raw={RAW} prepared={PREPARED} candidate={CANDIDATE} fixture={FIXTURE} postimage={POST}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for release in (False, True):
            exe = build(target, release)
            for descriptor, pool in ((True,0),(False,0),(False,1)):
                run_exact(exe, target, release, descriptor, pool)
    print("Six owned allocation receipts only; no GPU transfer, publication, caller refusal or gameplay proof.")

if __name__ == "__main__":
    main()
