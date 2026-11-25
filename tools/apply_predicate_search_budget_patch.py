#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bound recursive BDD meet searches to the compiler worker stack budget."""
import argparse
from pathlib import Path
import sys

BEFORE = "const MAX_MEET: usize = 1 << 16;"
AFTER = """// This search is recursive. Keep the depth bounded on compiler workers;
// exhaustion still returns the conservative answer (possible overlap).
const MAX_MEET: usize = 1 << 11;"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.checkout.resolve() / "crates/victory-shader/src/structure.rs"
    try:
        data = target.read_bytes()
        normalized = data.replace(b"\r\n", b"\n")
        before, after = BEFORE.encode(), AFTER.encode()
        if normalized.count(before) == 1:
            updated = normalized.replace(before, after)
        elif normalized.count(after) == 1:
            print("Predicate search budget patch is already present.")
            return 0
        else:
            raise ValueError("Predicate search budget source anchor differs.")
        if args.apply:
            target.write_bytes(updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated)
            print("Predicate search budget patch applied.")
        else:
            print("Predicate search source validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
