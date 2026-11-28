# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare an already-built-source disposable paired-wave checkout, dry-run by default.
No build, execution, production registration or CI dispatch.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "probes"))
import ai2_texback_selection_repair_transform as repair

UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
PREFIX = "crates/victory-gpu/src/"
PINS = {
    "tools/build_runtime.py": "31bc201ad006b304542e8b03405c1a9090d76804",
    "probes/ai2_texback_selection_repair_transform.py": "0e0f673cd6c60b05be0b2a68fb4a0b398ac8b6a5",
    "probes/ai2_texback_selection_repair.rs": "97485281a3d2863f302c72205e9c5527c3f757e4",
    "probes/ai2_texback_selection_observe.rs": "ac2ddc2d44ac86e7f638d760725be5b99298e243",
    "probes/ai2_texback_record_resource.rs": "80250d2d44288ba0d708f39c4ed674aec6bc5d30",
}
SOURCES = {
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
APPENDS = {
    PREFIX+"host.rs": ("probes/ai2_texback_selection_repair.rs", "8bea49c650a0eec442729ee7d3c12f16354af54d"),
    PREFIX+"texback.rs": ("probes/ai2_texback_selection_observe.rs", "75641b7edbefa66a69d81d144a9f637f0abbe7e4"),
    PREFIX+"resource.rs": ("probes/ai2_texback_record_resource.rs", "314c10076c9fa7f07a8fb24f69b4c44f3b758185"),
}

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
        if link(p) or p.resolve(strict=True) != p or repair.blob(lf(p.read_bytes())) != expected or repair.blob(git(ROOT,"show",f"HEAD:{path}")) != expected:
            raise ValueError("incorrect fixture input: "+path)
    before = inventory(root)
    for path, (raw, prepared) in SOURCES.items():
        p = root / path
        if p.resolve(strict=True) != p or repair.blob(git(root,"show",f"HEAD:{path}")) != raw or repair.blob(lf(p.read_bytes())) != prepared:
            raise ValueError("raw/prepared mismatch: "+path)
        print(f"source={path} raw={raw} prepared={prepared}")
    writes = {}
    for path, (probe, post) in APPENDS.items():
        original = (root/path).read_bytes()
        prepared = lf(original)
        name = Path(path).name
        corrected = repair.transform(name, prepared) if name in repair.PINS else prepared
        fixture = lf((ROOT/probe).read_bytes())
        proposed = corrected + b"\n" + fixture
        if not fixture or repair.blob(proposed) != post or proposed[:-len(fixture)-1] != corrected:
            raise ValueError("append postimage or inverse: "+path)
        writes[path] = (original, proposed)
        print(f"post={path} repaired={repair.blob(corrected)} postimage={post} bytes={len(proposed)}")
    if inventory(root) != before:
        raise ValueError("checkout changed during planning")
    if not args.apply:
        print(f"dry-run inventory_entries={len(before)} planned=3; no writes")
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
    print(f"applied inventory_entries={len(before)} changed=3 upstream={UPSTREAM}")

if __name__ == "__main__":
    main()
