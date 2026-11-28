# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated exact AI2 staging GPU transfer, not production registration."""
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
TEST = "texture::ai2_staging_gpu_transfer::actual_corrected_staging_gpu_transfer"
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

from preview_ai2_staging_bounds import transform

FIXTURE = "8ed4ab972a2b693ddb28a18259c4724df77f7033"
PREVIEW = "ebdd3e1148522d2a1e0ba31fdc23fa79441b4d4b"
CANDIDATE = "30d690616b8e215e3019e2c41d12287e247f92ad"
POST = "681d530256a0a555d3283041234fe731ef324d74"
FIXTURE_PATH = "probes/ai2_staging_gpu_transfer.rs"

def clean_env():
    return {k:v for k,v in os.environ.items()
            if not k.upper().startswith(("VICTORY_", "AI2_", "RUST_TEST_"))}

def run_process(args, target, env, timeout):
    try:
        r = subprocess.run(args, cwd=target, env=env, capture_output=True,
                           text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as e:
        print("timed out; later cases not run", flush=True)
        for stream in (e.stdout, e.stderr):
            if stream:
                print(stream.decode("utf-8", "replace") if isinstance(stream, bytes) else stream, flush=True)
        raise
    print(r.stdout, flush=True)
    print(r.stderr, flush=True)
    return r

def exact_result(r, name):
    tests = [l for l in r.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in r.stdout.splitlines() if l.startswith("test result:")]
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if r.returncode or tests != [f"test {name} ... ok"] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        raise ValueError("missing exact native receipt")

def run_exact(exe, target, release, pool):
    env = clean_env()
    env.update(VICTORY_D3D12_WARP="1", VICTORY_SWEEP="0",
               VICTORY_COMMITTED_QUERY="1", VICTORY_STAGING_POOL=str(pool),
               AI2_EXPECT_POOL=str(pool))
    print(f"profile={'release' if release else 'debug'} pool={pool} filter={TEST}", flush=True)
    r = run_process([str(exe), TEST, "--exact", "--test-threads=1", "--nocapture"],
                    target, env, 210)
    exact_result(r, TEST)
    adapters = re.findall(r"^transfer_adapter actual_high=(-?\d+) actual_low=(\d+) warp_high=(-?\d+) warp_low=(\d+) software=1\s*$", r.stderr, re.M)
    if len(adapters) != 1 or adapters[0][:2] != adapters[0][2:]:
        raise ValueError("adapter receipt")
    got = [tuple(map(int,x)) for x in re.findall(r"^staging_transfer case=(\d+) pool=(\d+) subresources=(\d+) logical=(\d+) required=(\d+) width=(\d+) active=(\d+) fence=(\d+)\s*$",r.stderr,re.M)]
    cases = [(1,260,512,8),(1,512,512,512),(6,3586,3840,84),(1,2824,3072,96),(1,272,512,32)]
    want = [(i,pool,n,logical,full,65536 if pool else full,active,1)
            for i,(n,logical,full,active) in enumerate(cases)]
    if got != want:
        raise ValueError("ordered GPU transfer receipts")

def main():
    if os.name != "nt":
        raise SystemExit("Windows WARP required")
    for path,pin in [("tools/build_runtime.py",BUILDER),("tools/preview_ai2_staging_bounds.py",PREVIEW),(FIXTURE_PATH,FIXTURE)]:
        if blob(git(ROOT,"show","HEAD:"+path)) != pin:
            raise ValueError("repository identity: "+path)
    with tempfile.TemporaryDirectory(prefix="ai1-staging-transfer-") as tmp:
        target = Path(tmp)/"runtime"
        subprocess.run([sys.executable,str(ROOT/"tools/build_runtime.py"),str(target),"--paired-wave-refresh"],
                       check=True,timeout=900,env=clean_env())
        if git(target,"rev-parse","HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        path=target/PATH
        original=path.read_bytes()
        prepared=original.replace(b"\r\n",b"\n")
        if blob(git(target,"show","HEAD:"+PATH))!=RAW or blob(prepared)!=PREPARED:
            raise ValueError("prepared identity")
        candidate=transform(prepared)
        fixture=(ROOT/FIXTURE_PATH).read_bytes().replace(b"\r\n",b"\n")
        post=candidate+b"\n"+fixture
        if (blob(candidate),blob(fixture),blob(post))!=(CANDIDATE,FIXTURE,POST):
            raise ValueError("postimage identity")
        path.write_bytes(post.replace(b"\n",b"\r\n") if b"\r\n" in original else post)
        if path.read_bytes().replace(b"\r\n",b"\n")!=post:
            raise ValueError("written identity")
        print(f"upstream={UPSTREAM} raw={RAW} prepared={PREPARED} candidate={CANDIDATE} fixture={FIXTURE} postimage={POST}",flush=True)
        subprocess.run(["git","diff","--check"],cwd=target,check=True)
        for release in (False,True):
            exe=build(target,release)
            print(f"executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}",flush=True)
            for pool in (0,1):
                run_exact(exe,target,release,pool)
    print("Four owned GPU transfer receipts only; no production upload, publication, failure recovery or gameplay.")

if __name__=="__main__":
    main()
