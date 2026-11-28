# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated actual baseline descriptor queue tests; no production changes."""
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
RAW = "7970fc5f0c3977bde0a81dbcec1a497384b933bc"
PREPARED = "13a6d0a94621d4a3609abed26cb07c6b6cc6a989"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
TEST = "descriptor::host::ai2_descriptor_retry_baseline::"
PATH = "crates/victory-gpu/src/descriptor/host.rs"

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

FIXTURE="11a1063ce95d8acbaa83330ed35036e619149f31"
POST="8a019f42ae470cf4b854a5cab0a1d5218e7e985e"
FIXTURE_PATH="probes/ai2_descriptor_retry_baseline.rs"
CASES=[
    ("actual_descriptor_generation_and_retry_bounds","descriptor_generation stale_writes=2 stale_operations=7 retry_steps=271 final_looks=255 done=1 shift_cap_steps=18 due_limits=7 current_room=1 stale_room=0 census_checks=4"),
    ("actual_descriptor_retry_retains_prior_metadata","descriptor_retry_baseline retained_fingerprint=1 retained_mapped=48 partly_zero_mapped=1 new_generation_reset=1 combined_retained_mapped=24 combined_retained_fingerprint=1"),
]

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

def main():
    if os.name!="nt":
        raise SystemExit("Windows native required")
    for p,pin in [("tools/build_runtime.py",BUILDER),(FIXTURE_PATH,FIXTURE)]:
        if blob(git(ROOT,"show","HEAD:"+p))!=pin:
            raise ValueError("repository identity: "+p)
    with tempfile.TemporaryDirectory(prefix="ai1-descriptor-retry-") as tmp:
        target=Path(tmp)/"runtime"
        subprocess.run([sys.executable,str(ROOT/"tools/build_runtime.py"),str(target),"--paired-wave-refresh"],
                       check=True,timeout=900,env=clean_env())
        if git(target,"rev-parse","HEAD").decode().strip()!=UPSTREAM:
            raise ValueError("upstream identity")
        path=target/PATH
        original=path.read_bytes()
        prepared=original.replace(b"\r\n",b"\n")
        fixture=(ROOT/FIXTURE_PATH).read_bytes().replace(b"\r\n",b"\n")
        if blob(git(target,"show","HEAD:"+PATH))!=RAW or blob(prepared)!=PREPARED or blob(fixture)!=FIXTURE:
            raise ValueError("source identity")
        if b"mod ai2_descriptor_retry_baseline" in prepared:
            raise ValueError("duplicate fixture")
        post=prepared+b"\n"+fixture
        if blob(post)!=POST:
            raise ValueError("postimage identity")
        path.write_bytes(post.replace(b"\n",b"\r\n") if b"\r\n" in original else post)
        if path.read_bytes().replace(b"\r\n",b"\n")!=post:
            raise ValueError("written identity")
        print(f"upstream={UPSTREAM} raw={RAW} prepared={PREPARED} fixture={FIXTURE} postimage={POST}",flush=True)
        subprocess.run(["git","diff","--check"],cwd=target,check=True)
        for release in (False,True):
            exe=build(target,release)
            print(f"profile={'release' if release else 'debug'} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}",flush=True)
            listing=run_process([str(exe),"--list"],target,clean_env(),60)
            if listing.returncode or any(listing.stdout.splitlines().count(TEST+name+": test")!=1 for name,_ in CASES):
                raise ValueError("exact test listing")
            for name,receipt in CASES:
                name=TEST+name
                print(f"profile={'release' if release else 'debug'} filter={name}",flush=True)
                r=run_process([str(exe),name,"--exact","--test-threads=1","--nocapture"],target,clean_env(),60)
                exact_result(r,name)
                if [l for l in r.stderr.splitlines() if l.startswith(receipt.split()[0]+" ")]!=[receipt]:
                    raise ValueError("baseline assertion receipt")
    print("Four owned baseline descriptor receipts only; no actual failed upload, production repair or gameplay.")

if __name__=="__main__":
    main()
