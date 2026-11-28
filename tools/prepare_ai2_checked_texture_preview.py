# SPDX-License-Identifier: GPL-3.0-or-later
"""Checked-texture preview scratch-only preparation, dry-run by default; no build or CI dispatch."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
PREFIX = "crates/victory-gpu/src/"
PINS = {
    "patches/ai2-checked-texture-preview-common-r2.patch": "57431b71dc138f7f82c82ea97dd60977530ffeda",
    "patches/ai2-checked-texture-preview.patch": "b007b798e789a766b4293ea9643fe259f1e6e02d",
    "tools/build_runtime.py": "31bc201ad006b304542e8b03405c1a9090d76804",
}
SOURCES = {
    PREFIX+"list.rs": ("3bf89f3c9b17f14c2ec4fa4480e3378e6ac8857e",)*2,
    PREFIX+"host.rs": ("458d146aedf6f13dac80782d283a048d80e4a931", "88acbb3b2cf550cdf2303685fcc32249f9e46328"),
    PREFIX+"texback.rs": ("3102a4f9ed2f80c86a28fcc5070b855143279574",)*2,
    PREFIX+"resource.rs": ("1fff3d6a42db6d2eea17de0b7d325ebec5eb6dfc", "215122c8728e95b3748b135f6c760f0690a959d8"),
    PREFIX+"watch.rs": ("9cf4bc6d686efc56e8bb65bea49c233ace2f8223", "66ce0fb3d6f3e8b72b2a9efdca04135222c6eb07"),
    PREFIX+"descriptor/host.rs": ("7970fc5f0c3977bde0a81dbcec1a497384b933bc", "13a6d0a94621d4a3609abed26cb07c6b6cc6a989"),
    PREFIX+"copystat.rs": ("2e43271583d232efa5def942d3bdae50b2f1d61e",)*2,
    "crates/victory-formats/src/texture.rs": ("fa719c93953d9e6589c4d2cd27a13d773863c316",)*2,
    "crates/victory-gpu/Cargo.toml": ("e6d844522016d5bb476dc04ad972b0e0498d7c86",)*2,
    "Cargo.toml": ("4e21b692d66103d990003164b6f1e4f700bc4086",)*2,
    "Cargo.lock": ("29bab8c72233fbd9552e646c79316bc9439df0d7",)*2,
}
COMMON = {
    PREFIX+"host.rs": "031a65c12bbab967759383b2a75a3be46c46bbde",
    PREFIX+"texback.rs": "a17dfb5f693163d64ab8f4a60ede71e52c2f596a",
}
PATCH = "patches/ai2-checked-texture-preview-common-r2.patch"
PREVIEW = "patches/ai2-checked-texture-preview.patch"
POST = "ab963b02ad9a4e68a5fa45513e543d15ab67e41c"

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def transform(data, patch, path, expected):
    label = ("a/"+path+" b/"+path+"\n").encode()
    blocks = [b for b in patch.split(b"diff --git ") if b.startswith(label)]
    if len(blocks) != 1:
        raise ValueError("common patch path")
    import re
    hunks = re.split(rb"(?m)^@@[^\n]*\n", blocks[0])[1:]
    if not hunks:
        raise ValueError("missing common hunks")
    out = data
    inverse = []
    for hunk in hunks:
        rows = [l for l in hunk.split(b"\n") if l[:1] in (b" ", b"+", b"-")]
        before = b"\n".join(l[1:] for l in rows if l[:1] != b"+") + b"\n"
        after = b"\n".join(l[1:] for l in rows if l[:1] != b"-") + b"\n"
        if out.count(before) != 1:
            raise ValueError("nonunique common anchor")
        out = out.replace(before, after, 1)
        inverse.append((before, after))
    restored = out
    for before, after in reversed(inverse):
        if restored.count(after) != 1:
            raise ValueError("nonunique common inverse")
        restored = restored.replace(after, before, 1)
    if restored != data or blob(out) != expected:
        raise ValueError("common postimage/inverse")
    return out

def lf(data):
    return data.replace(b"\r\n", b"\n")

def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)

def link(p):
    return p.is_symlink() or p.is_junction()

def inventory(root):
    result = {}
    def walk(d):
        for p in sorted(d.iterdir()):
            rel = p.relative_to(root).as_posix()
            if rel == ".git":
                continue
            if link(p):
                raise ValueError("unexpected link: "+rel)
            if p.is_dir():
                result[rel] = ("dir",)
                walk(p)
            elif p.is_file():
                with p.open("rb") as f:
                    result[rel] = ("file", hashlib.file_digest(f, "sha256").hexdigest())
            else:
                raise ValueError("unexpected path: "+rel)
    walk(root)
    return result

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkout", type=Path)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    supplied = args.checkout.absolute()
    root = supplied.resolve(strict=True)
    if link(supplied) or supplied != root or not root.is_dir() or root == ROOT or ROOT in root.parents or root in ROOT.parents:
        raise ValueError("require separate canonical disposable checkout")
    if link(root / ".git") or not (root / ".git").is_dir():
        raise ValueError("require independent ordinary git checkout")
    if Path(os.fsdecode(git(root,"rev-parse","--show-toplevel").strip())).resolve() != root:
        raise ValueError("incorrect checkout root")
    if git(root,"rev-parse","HEAD").decode().strip() != UPSTREAM:
        raise ValueError("incorrect upstream")
    for path, expected in PINS.items():
        p = ROOT / path
        if link(p) or p.resolve(strict=True) != p or blob(lf(p.read_bytes())) != expected or blob(git(ROOT,"show",f"HEAD:{path}")) != expected:
            raise ValueError("incorrect preview input: "+path)
    before = inventory(root)
    for path, (raw, prepared) in SOURCES.items():
        p = root / path
        if p.resolve(strict=True) != p or blob(git(root,"show",f"HEAD:{path}")) != raw or blob(lf(p.read_bytes())) != prepared:
            raise ValueError("raw/prepared mismatch: "+path)
        print(f"source={path} raw={raw} prepared={prepared}")
    writes = {}
    patch = lf((ROOT/PATCH).read_bytes())
    for path in COMMON:
        original = (root/path).read_bytes()
        corrected = transform(lf(original), patch, path, COMMON[path])
        writes[path] = (original, corrected)
        print(f"common={path} postimage={blob(corrected)}")
    path = PREFIX+"texback.rs"
    original, corrected = writes[path]
    proposed = transform(corrected, lf((ROOT/PREVIEW).read_bytes()), path, POST)
    if not proposed.startswith(corrected) or proposed == corrected:
        raise ValueError("preview must be additive")
    writes[path] = (original, proposed)
    print(f"preview={path} repaired={blob(corrected)} postimage={POST} bytes={len(proposed)}")
    if inventory(root) != before:
        raise ValueError("checkout changed during planning")
    if not args.apply:
        print(f"dry-run inventory_entries={len(before)} planned=2; no writes")
        return
    for path, (original, proposed) in writes.items():
        p = root/path
        if p.resolve(strict=True) != p or p.read_bytes() != original:
            raise ValueError("changed before write: "+path)
        p.write_bytes(proposed)
    after = inventory(root)
    if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != set(writes):
        raise ValueError("unexpected inventory delta")
    for path, (_, proposed) in writes.items():
        if (root/path).read_bytes() != proposed:
            raise ValueError("actual postimage mismatch: "+path)
    subprocess.run(["git","diff","--check"],cwd=root,check=True)
    print(f"applied inventory_entries={len(before)} changed=2 upstream={UPSTREAM}")

if __name__ == "__main__":
    main()
