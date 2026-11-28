#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the caller-free terminal preview to a disposable paired checkout."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
LIB = "crates/victory-gpu/src/lib.rs"
MODULE = "crates/victory-gpu/src/delivery_terminal.rs"
PRE = "19b54e622e9ff880de09bb06a349323b71ce348a"
POST = "bfa6093d3df202ef0eca4d855d86bb424cc47f30"
NEW = "912d6f3a972d0ce6067ee31db30069fcb32a6c8a"
PATCH = "5342aa50c85b607977e25fbcb1fc7c58d4445054"
# Conservative literal screen, not a semantic analysis of exit statuses.
STATUS = re.compile(
    rb"(?i)" + rb"_*".join(bytes([c]) for c in b"e6000001")
    + rb"|" + rb"_*".join(bytes([c]) for c in b"3858759681")
    + rb"|-\s*" + rb"_*".join(bytes([c]) for c in b"436207615")
)


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def lf(data):
    return data.replace(b"\r\n", b"\n")


def git(root, *args, data=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=root, input=data, check=True,
                          env=env, stdout=subprocess.PIPE).stdout


def ordinary(path, directory):
    if path.is_symlink() or path.is_junction():
        raise ValueError("Unexpected link/junction: " + str(path))
    info = path.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("Expected ordinary directory: " + str(path))
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Expected ordinary unaliased file: " + str(path))
    return info.st_dev, info.st_ino


def root_identity(root):
    for ancestor in (*reversed(root.parents), root):
        ordinary(ancestor, directory=True)
    if root.resolve(strict=True) != root:
        raise ValueError("Checkout path must be canonical")
    root_id = ordinary(root, directory=True)
    gitdir = root / ".git"
    git_id = ordinary(gitdir, directory=True)
    common = gitdir / "commondir"
    if common.exists() or common.is_symlink() or common.is_junction():
        raise ValueError("Shared Git common directory is not allowed")
    for args, expected in [
        (("rev-parse", "--show-toplevel"), root),
        (("rev-parse", "--absolute-git-dir"), gitdir),
        (("rev-parse", "--path-format=absolute", "--git-common-dir"), gitdir),
    ]:
        observed = Path(git(root, *args).decode("utf-8").strip())
        if observed.resolve(strict=True) != expected or not observed.samefile(expected):
            raise ValueError("Unexpected Git checkout identity: " + str(observed))
    if git(root, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
        raise ValueError("Wrong pinned upstream")
    return root_id, git_id


def inventory(root, scan_status=False):
    result = {}
    seen = {ordinary(root, directory=True), ordinary(root / ".git", directory=True)}

    def walk(directory):
        for path in sorted(directory.iterdir()):
            name = path.relative_to(root).as_posix()
            if name == ".git":
                continue
            if path.is_symlink() or path.is_junction():
                raise ValueError("Unexpected link/junction: " + name)
            is_directory = path.is_dir()
            identity = ordinary(path, directory=is_directory)
            if identity in seen:
                raise ValueError("Aliased inventory entry: " + name)
            seen.add(identity)
            if is_directory:
                result[name] = ("dir",)
                walk(path)
            else:
                data = path.read_bytes()
                if scan_status and STATUS.search(data):
                    raise ValueError("Possible status collision: " + name)
                result[name] = ("file", hashlib.sha256(data).hexdigest())
    walk(root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    ns = parser.parse_args()
    try:
        if sys.version_info < (3, 12):
            raise ValueError("Python 3.12+ required for junction checks")
        root = ns.checkout.absolute()
        own = Path(__file__).resolve().parent.parent
        if root == own or own in root.parents or root in own.parents:
            raise ValueError("Use a separate disposable prepared checkout")
        identity = root_identity(root)

        def snapshot(scan_status=False):
            if root_identity(root) != identity:
                raise ValueError("Checkout root identity changed")
            result = inventory(root, scan_status=scan_status)
            if root_identity(root) != identity:
                raise ValueError("Checkout root identity changed")
            return result

        before = snapshot(scan_status=True)
        if (before.get(LIB, (None,))[0] != "file"
                or blob(lf((root / LIB).read_bytes())) != PRE or MODULE in before):
            raise ValueError("Wrong prepared lib or module already exists")
        patch = lf((own / "patches/ai6-delivery-terminal-preview.patch").read_bytes())
        if blob(patch) != PATCH:
            raise ValueError("Wrong canonical patch bytes")
        git(root, "apply", "--check", "-", data=patch)
        if snapshot() != before:
            raise ValueError("Dry check changed checkout; discard checkout")
        if not ns.apply:
            print("Dry check: exact pins, full inventory/status scan unchanged")
            return 0

        def apply_and_verify():
            git(root, "apply", "-", data=patch)
            after = snapshot()
            for name, pin in ((LIB, POST), (MODULE, NEW)):
                if after.get(name, (None,))[0] != "file" or blob(lf((root / name).read_bytes())) != pin:
                    raise ValueError("Wrong canonical postimage: " + name)
            expected = dict(before)
            expected.update({LIB: after[LIB], MODULE: after[MODULE]})
            if after != expected:
                raise ValueError("Unexpected inventory delta; discard checkout")
            return after

        after = apply_and_verify()
        git(root, "apply", "--reverse", "--check", "-", data=patch)
        if snapshot() != after:
            raise ValueError("Reverse check changed checkout; discard checkout")
        git(root, "apply", "--reverse", "-", data=patch)
        if snapshot() != before:
            raise ValueError("Inverse did not restore exact raw inventory; discard checkout")
        if apply_and_verify() != after:
            raise ValueError("Reapply did not reproduce exact raw inventory; discard checkout")
        git(root, "diff", "--check")
        if snapshot() != after:
            raise ValueError("Final inventory changed; discard checkout")
        print("Applied preview; exact two-path inventory delta, inverse and reapply verified")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, UnicodeError) as exc:
        parser.exit(1, f"Terminal preview preparation failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
