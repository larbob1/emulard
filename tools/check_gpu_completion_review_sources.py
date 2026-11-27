#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only source identity gate for the frozen #18 GPU completion review.

This is not runtime preparation, native validation, or an approval to modify
the reviewed paths. Pins are independently projected LF-normalized Git blobs.
"""
import argparse
import hashlib
from pathlib import Path

BASE = "dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1"
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
PREFIX = "crates/victory-gpu/src/"
PINS = {
    PREFIX + "host.rs": "88acbb3b2cf550cdf2303685fcc32249f9e46328",
    PREFIX + "shadow.rs": "40f1ae02506de251d51e00ebfd36f58e58e7621b",
    PREFIX + "texback.rs": "3102a4f9ed2f80c86a28fcc5070b855143279574",
    PREFIX + "queue2.rs": "6d016d270e6de310231f7cbc4c470c3373910c79",
    PREFIX + "list.rs": "3bf89f3c9b17f14c2ec4fa4480e3378e6ac8857e",
}


def blob_id(data):
    data = data.replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def verify(checkout, pins=PINS):
    """Return fixed relative path, observed hash (or None), and match status."""
    rows = []
    for relative, expected in pins.items():
        try:
            path = checkout / relative
            # Do not follow symlinks outside the supplied checkout.
            if not path.resolve().is_relative_to(checkout.resolve()):
                raise ValueError("outside checkout")
            actual = blob_id(path.read_bytes())
        except (OSError, ValueError, RuntimeError):
            actual = None
        rows.append((relative, actual, actual == expected))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="already prepared isolated #18 checkout")
    args = parser.parse_args(argv)
    print("GPU source review base=" + BASE + " upstream=" + UPSTREAM)
    rows = verify(args.checkout)
    for relative, actual, match in rows:
        print(relative, "match" if match else "MISMATCH",
              actual or "unreadable", "expected=" + PINS[relative])
    if not all(match for _, _, match in rows):
        print("GPU source review gate: refused")
        return 1
    print("GPU source review gate: five identities match (source only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
