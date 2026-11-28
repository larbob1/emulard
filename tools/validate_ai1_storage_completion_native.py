# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated baseline owned storage completion gate, no production registration."""
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
RAW = "5fe9aba9aa336dcaace3c21e72040de4efb1e0dd"
PREPARED = "bee5b9d71cb8f11c060b798485bd8e68391b36bd"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
TEST = "modules::dstorage::tests::storage_completion_native_"
PATH = "crates/victory-hle/src/modules/dstorage.rs"

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)

def build(target, release):
    args = ["cargo", "test", "--locked", "-p", "victory-hle", "--lib", "--features",
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
                and obj.get("target", {}).get("name") == "victory_hle"
                and obj.get("profile", {}).get("test") is True):
            artifacts.append(Path(obj["executable"]).resolve())
    if len(artifacts) != 1 or not artifacts[0].is_file() or not artifacts[0].is_relative_to(target.resolve()):
        raise ValueError(f"unexpected test executables: {artifacts}")
    return artifacts[0]

FIXTURE = "215ab1daa0b9c228c5ebc12d3ee58cbe800e8ad9"
POST = "70c977285324e2c8cfc205372f1e276f6d27e4b4"
FIXTURE_PATH = "probes/storage_completion_native.rs"
ANCHOR = b"    #[test]\n    fn raw_and_zlib_reads_from_a_file() {"
NAMES = [TEST + "address", TEST + "pages"]

def clean_env():
    return {k:v for k,v in os.environ.items()
            if not k.upper().startswith(("VICTORY_", "RUST_TEST_"))}

def run_exact(exe, target, release):
    env = clean_env()
    print(f"profile={'release' if release else 'debug'} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("test env: inherited VICTORY_* and RUST_TEST_* removed; storage defaults retained", flush=True)
    listing = subprocess.run([str(exe), "--list", "--ignored"], cwd=target, env=env,
                             capture_output=True, text=True, errors="replace", timeout=60)
    print(listing.stdout, flush=True)
    print(listing.stderr, flush=True)
    if listing.returncode or any(listing.stdout.splitlines().count(name + ": test") != 1 for name in NAMES):
        raise ValueError("exact ignored test listing")
    for name in NAMES:
        print(f"profile={'release' if release else 'debug'} filter={name}", flush=True)
        r = subprocess.run([str(exe), name, "--exact", "--ignored", "--test-threads=1", "--format", "pretty"],
                           cwd=target, env=env, capture_output=True, text=True,
                           errors="replace", timeout=60)
        print(r.stdout, flush=True)
        print(r.stderr, flush=True)
        tests = [l for l in r.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
        summaries = [l for l in r.stdout.splitlines() if l.startswith("test result:")]
        summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
        if r.returncode or tests != [f"test {name} ... ok"] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
            raise ValueError("missing exact owned storage completion receipt")

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    if blob(git(ROOT, "show", "HEAD:tools/build_runtime.py")) != BUILDER:
        raise ValueError("builder identity")
    if blob(git(ROOT, "show", "HEAD:" + FIXTURE_PATH)) != FIXTURE:
        raise ValueError("fixture git identity")
    with tempfile.TemporaryDirectory(prefix="ai1-storage-completion-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900, env=clean_env())
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        path = target / PATH
        original = path.read_bytes()
        prepared = original.replace(b"\r\n", b"\n")
        fixture = (ROOT / FIXTURE_PATH).read_bytes().replace(b"\r\n", b"\n")
        if blob(git(target, "show", "HEAD:" + PATH)) != RAW or blob(prepared) != PREPARED or blob(fixture) != FIXTURE:
            raise ValueError("source identity")
        if prepared.count(ANCHOR) != 1 or any(name.split("::")[-1].encode() in prepared for name in NAMES):
            raise ValueError("fixture anchor or duplicate")
        inserted = fixture.rstrip() + b"\n\n"
        post = prepared.replace(ANCHOR, inserted + ANCHOR, 1)
        if blob(post) != POST or post.replace(inserted + ANCHOR, ANCHOR, 1) != prepared:
            raise ValueError("fixture postimage or inverse identity")
        path.write_bytes(post.replace(b"\n", b"\r\n") if b"\r\n" in original else post)
        if path.read_bytes().replace(b"\r\n", b"\n") != post:
            raise ValueError("written identity")
        print(f"upstream={UPSTREAM} raw={RAW} prepared={PREPARED} fixture={FIXTURE} postimage={POST}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for release in (False, True):
            run_exact(build(target, release), target, release)
    print("Four baseline owned storage completion receipts only; no precise status-time visibility, cleanup proof, timing or gameplay.")

if __name__ == "__main__":
    main()
