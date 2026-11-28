# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare disposable file-lifetime native fixture; no build or launch."""
import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATH = "crates/victory-hle/src/modules/dstorage.rs"
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
RAW = "5fe9aba9aa336dcaace3c21e72040de4efb1e0dd"
PREPARED = "bee5b9d71cb8f11c060b798485bd8e68391b36bd"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
FIXTURE = "3860879590b6123c2609b6059a03d1ff7a40ae3d"
POST = "cde18978122629f60de820d419fc189367dae142"
OLD = "static FILE_VTABLE: Methods<8> = Methods([\n    missing::<0> as *const (),\n    add_ref_instance::<File> as *const (),\n    release::<File> as *const (),"
NEW = "#[cfg(not(test))]\nconst FILE_RELEASE_SLOT: extern \"system\" fn(*mut Instance<File>) -> u32 = release::<File>;\n#[cfg(test)]\nconst FILE_RELEASE_SLOT: extern \"system\" fn(*mut Instance<File>) -> u32 = tests::file_release_review;\n\nstatic FILE_VTABLE: Methods<8> = Methods([\n    missing::<0> as *const (),\n    add_ref_instance::<File> as *const (),\n    FILE_RELEASE_SLOT as *const (),"
ANCHOR = "    #[test]\n    fn raw_and_zlib_reads_from_a_file() {"

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)

def unique(source, old, new):
    if source.count(old) != 1:
        raise ValueError("nonunique anchor")
    return source.replace(old, new, 1)

def transform(source, fixture):
    inserted = fixture.rstrip() + "\n\n" + ANCHOR
    result = unique(unique(source, OLD, NEW), ANCHOR, inserted)
    if unique(unique(result, inserted, ANCHOR), NEW, OLD) != source:
        raise ValueError("inverse mismatch")
    if blob(result.encode()) != POST:
        raise ValueError("postimage mismatch")
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.checkout.absolute()
    if target != target.resolve() or target == ROOT or ROOT in target.parents or target in ROOT.parents:
        raise ValueError("separate canonical checkout required")
    root = Path(git(target, "rev-parse", "--show-toplevel").decode().strip())
    if not root.samefile(target):
        raise ValueError("checkout root required")
    if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
        raise ValueError("pinned upstream checkout required")
    if blob(git(ROOT, "show", "HEAD:tools/build_runtime.py")) != BUILDER:
        raise ValueError("builder identity")
    if blob(git(target, "show", "HEAD:" + PATH)) != RAW:
        raise ValueError("raw identity")
    path = target / PATH
    if path.resolve() != path or not path.is_file():
        raise ValueError("nonsymlink prepared source required")
    original = path.read_bytes()
    source = original.replace(b"\r\n", b"\n")
    fragment = (ROOT / "probes/storage_file_lifetime_native.rs").read_bytes().replace(b"\r\n", b"\n")
    if blob(source) != PREPARED or blob(fragment) != FIXTURE:
        raise ValueError("prepared/fixture identity")
    post = transform(source.decode(), fragment.decode()).encode()
    if args.apply:
        if path.resolve() != path or path.read_bytes() != original:
            raise ValueError("prepared source changed")
        written = post.replace(b"\n", b"\r\n") if b"\r\n" in original else post
        path.write_bytes(written)
        if path.read_bytes() != written:
            raise ValueError("written identity")
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
    print(f"raw={RAW} prepared={PREPARED} fixture={FIXTURE} postimage={POST}")

if __name__ == "__main__":
    main()
