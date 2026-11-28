#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the caller-free terminal preview to a disposable paired checkout."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess

UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
LIB = "crates/victory-gpu/src/lib.rs"
MODULE = "crates/victory-gpu/src/delivery_terminal.rs"
PRE = "19b54e622e9ff880de09bb06a349323b71ce348a"
POST = "bfa6093d3df202ef0eca4d855d86bb424cc47f30"
NEW = "912d6f3a972d0ce6067ee31db30069fcb32a6c8a"
PATCH = "5342aa50c85b607977e25fbcb1fc7c58d4445054"
STATUS = re.compile(rb"(?i)e600_?0001|3858759681|3_858_759_681|-436207615")

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def git(root, *args, data=None):
    return subprocess.run(["git", *args], cwd=root, input=data, check=True,
                          stdout=subprocess.PIPE).stdout

def inventory(root, scan_status=False):
    names = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    result = {}
    for name in set(names.decode("utf-8").split("\0")) - {""}:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing/nonregular inventory entry: " + name)
        data = path.read_bytes()
        if scan_status and STATUS.search(data):
            raise ValueError("Possible status collision: " + name)
        result[name] = blob(data)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    ns = parser.parse_args()
    root = ns.checkout.resolve()
    own = Path(__file__).resolve().parent.parent
    try:
        if root == own or own in root.parents or root in own.parents:
            raise ValueError("Use a separate disposable prepared checkout")
        if git(root, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("Wrong pinned upstream")
        if Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
            raise ValueError("Checkout must be repository root")
        before = inventory(root, scan_status=True)
        if before.get(LIB) != PRE or MODULE in before or (root / MODULE).exists():
            raise ValueError("Wrong prepared lib or module already exists")
        patch = (own / "patches/ai6-delivery-terminal-preview.patch").read_bytes()
        if blob(patch) != PATCH:
            raise ValueError("Wrong patch bytes")
        git(root, "apply", "--check", "-", data=patch)
        if not ns.apply:
            print("Dry check: pinned lib, patch, status scan; no changes")
            return 0
        git(root, "apply", "-", data=patch)
        after = inventory(root)
        expected = dict(before)
        expected.update({LIB: POST, MODULE: NEW})
        if after != expected:
            raise ValueError("Unexpected inventory delta; discard checkout")
        git(root, "apply", "--reverse", "--check", "-", data=patch)
        git(root, "diff", "--check")
        print("Applied preview; exact two-path inventory delta and inverse check")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, UnicodeError) as exc:
        parser.exit(1, f"Terminal preview preparation failed: {exc}\n")

if __name__ == "__main__":
    raise SystemExit(main())
