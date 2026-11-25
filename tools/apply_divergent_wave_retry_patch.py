#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Retry split-wave shaders when their barriers cross divergent branches."""
import argparse
from pathlib import Path
import sys

BEFORE = '''pub(super) fn needs_every_lane(what: &str) -> bool {
    what.ends_with("where not every lane runs") || what == MASK_ELSEWHERE
}'''
AFTER = '''pub(super) fn needs_every_lane(what: &str) -> bool {
    what.ends_with("where not every lane runs")
        || what == MASK_ELSEWHERE
        || what == "group-wide meetings in independently branching console waves"
}'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.checkout.resolve() / "crates/victory-shader/src/emit/lower.rs"
    try:
        data = target.read_bytes()
        normalized = data.replace(b"\r\n", b"\n")
        before, after = BEFORE.encode(), AFTER.encode()
        if normalized.count(before) == 1:
            updated = normalized.replace(before, after)
        elif normalized.count(after) == 1:
            print("Divergent-wave retry patch is already present.")
            return 0
        else:
            raise ValueError("Wave retry source anchor differs.")
        if args.apply:
            target.write_bytes(updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated)
            print("Divergent-wave retry patch applied.")
        else:
            print("Wave retry source validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
