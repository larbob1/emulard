# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare isolated test-only W0/W1 worker fixture. No build or test launch."""
import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATH = "crates/victory-hle/src/modules/dstorage.rs"
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
RAW = "5fe9aba9aa336dcaace3c21e72040de4efb1e0dd"
PREPARED = "bee5b9d71cb8f11c060b798485bd8e68391b36bd"
EXECUTE = "1b2d667447f5f3f0f94fcc25f224ffb3e1869277"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
FIXTURE = "143131011a9be1cfa39fee828f5369489bfd3ffd"
POST = "59358fe65fbc835d86a6ddfa493dfacf943b0811"
START = "fn execute(request: &Request) -> Result<(), HRESULT> {"
END = "\n/// Inflates a zlib stream into `out`, returning the bytes written."
SIGNATURE = "fn execute_scratch_review(request: &Request, scratch: &mut NativeScratch) -> Result<(), HRESULT> {"
OLD = "            let mut data = vec![0; size];\n            read_into(request, &mut data)?;\n            out.copy_from_slice(&data);\n            Ok(size)"
NEW = "            scratch.run(size, |data| {\n                read_into(request, data)?;\n                out.copy_from_slice(data);\n                Ok(size)\n            })"
ANCHOR = "    #[test]\n    fn raw_and_zlib_reads_from_a_file() {"
REPLACEMENTS = [
    [
        "        tracing::info!(workers = started, \"dstorage: workers\");",
        "        #[cfg(test)]\n        tests::worker_probe_spawned(started);\n        tracing::info!(workers = started, \"dstorage: workers\");"
    ],
    [
        "    let mut lanes = scheduler.lock();\n    loop {\n        let Some(job) = lanes.start() else {",
        "    #[cfg(test)]\n    let mut worker_probe = tests::WorkerProbe::new();\n    let mut lanes = scheduler.lock();\n    loop {\n        let Some(job) = lanes.start() else {"
    ],
    [
        "        let result = execute(&job.request);",
        "        #[cfg(not(test))]\n        let result = execute(&job.request);\n        #[cfg(test)]\n        let result = match worker_probe.as_mut() {\n            Some(probe) => probe.run(&job),\n            None => execute(&job.request),\n        };"
    ]
]

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)

def unique(source, old, new):
    if source.count(old) != 1:
        raise ValueError("nonunique anchor")
    return source.replace(old, new, 1)

def execute_slice(source):
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("execute boundary")
    begin = source.index(START)
    return source[begin:source.index(END, begin)]

def transform(source, fixture):
    original = execute_slice(source)
    if blob(original.encode()) != EXECUTE:
        raise ValueError("execute pin")
    clone = unique(unique(original.rstrip(), START, SIGNATURE), OLD, NEW)
    if unique(unique(clone, SIGNATURE, START), NEW, OLD) != original.rstrip():
        raise ValueError("clone inverse")
    result = source
    for old, new in REPLACEMENTS:
        result = unique(result, old, new)
    inserted = clone + "\n\n" + fixture.rstrip() + "\n\n"
    result = unique(result, ANCHOR, inserted + ANCHOR)
    inverse = unique(result, inserted + ANCHOR, ANCHOR)
    for old, new in reversed(REPLACEMENTS):
        inverse = unique(inverse, new, old)
    if inverse != source or execute_slice(result) != original or blob(result.encode()) != POST:
        raise ValueError("postimage/inverse")
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.checkout.absolute()
    if target != target.resolve() or target == ROOT or ROOT in target.parents or target in ROOT.parents:
        raise ValueError("separate nonsymlink checkout required")
    if Path(git(target, "rev-parse", "--show-toplevel").decode().strip()).resolve() != target:
        raise ValueError("checkout root required")
    if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
        raise ValueError("isolated pinned upstream checkout required")
    if blob(git(ROOT, "show", "HEAD:tools/build_runtime.py")) != BUILDER:
        raise ValueError("builder identity")
    if blob(git(target, "show", "HEAD:" + PATH)) != RAW:
        raise ValueError("raw identity")
    path = target / PATH
    if path.resolve() != path or not path.is_file():
        raise ValueError("nonsymlink prepared source required")
    original = path.read_bytes()
    source = original.replace(b"\r\n", b"\n")
    fragment = (ROOT / "probes/storage_worker_native.rs").read_bytes().replace(b"\r\n", b"\n")
    if blob(source) != PREPARED or blob(fragment) != FIXTURE:
        raise ValueError("prepared/fixture identity")
    post = transform(source.decode(), fragment.decode()).encode()
    if args.apply:
        if path.resolve() != path or path.read_bytes() != original:
            raise ValueError("prepared source changed before write")
        written = post.replace(b"\n", b"\r\n") if b"\r\n" in original else post
        path.write_bytes(written)
        if path.read_bytes() != written:
            raise ValueError("written identity")
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
    print(f"raw={RAW} prepared={PREPARED} execute={EXECUTE} fixture={FIXTURE} postimage={POST}")

if __name__ == "__main__":
    main()
