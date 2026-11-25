#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Give shader pipeline workers enough stack for deep shader lowering."""
import argparse
from pathlib import Path
import sys

BEFORE = '''            let spawned = std::thread::Builder::new()
                .name(format!("victory-pipelines-{i}"))
                .spawn(|| {'''
AFTER = '''            let spawned = std::thread::Builder::new()
                .name(format!("victory-pipelines-{i}"))
                // A few large console shaders recurse deeply during lowering.
                // Keep that work on a dedicated, bounded 8 MiB stack.
                .stack_size(8 * 1024 * 1024)
                .spawn(|| {'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.checkout.resolve() / "crates/victory-gpu/src/pipeline/make.rs"
    try:
        data = target.read_bytes()
        normalized = data.replace(b"\r\n", b"\n")
        before = BEFORE.encode()
        after = AFTER.encode()
        if normalized.count(before) == 1:
            updated = normalized.replace(before, after)
        elif normalized.count(after) == 1:
            print("Pipeline worker stack patch is already present.")
            return 0
        else:
            raise ValueError("Pipeline worker source anchor differs.")
        if args.apply:
            target.write_bytes(updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated)
            print("Pipeline worker stack patch applied.")
        else:
            print("Pipeline worker source validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
