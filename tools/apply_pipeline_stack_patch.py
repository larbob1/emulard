#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Give shader pipeline workers enough stack for deep shader lowering."""
import argparse
from pathlib import Path
import sys

BEFORE = '''            let spawned = std::thread::Builder::new()
                .name(format!("victory-pipelines-{i}"))
                .spawn(|| {'''
AFTER_8 = '''            let spawned = std::thread::Builder::new()
                .name(format!("victory-pipelines-{i}"))
                // A few large console shaders recurse deeply during lowering.
                // Keep that work on a dedicated, bounded 8 MiB stack.
                .stack_size(8 * 1024 * 1024)
                .spawn(|| {'''
AFTER = '''            let spawned = std::thread::Builder::new()
                .name(format!("victory-pipelines-{i}"))
                // Large console shaders need a deeper call stack during lowering.
                // Reserve a bounded 32 MiB stack for each compiler worker.
                .stack_size(32 * 1024 * 1024)
                .spawn(|| {'''

def patch_source(data: bytes) -> bytes:
    normalized = data.replace(b"\r\n", b"\n")
    before = BEFORE.encode()
    after = AFTER.encode()
    old = AFTER_8.encode()
    if normalized.count(before) == 1:
        return normalized.replace(before, after)
    if normalized.count(old) == 1:
        return normalized.replace(old, after)
    if normalized.count(after) == 1:
        return normalized
    raise ValueError("Pipeline worker source anchor differs.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.checkout.resolve() / "crates/victory-gpu/src/pipeline/make.rs"
    try:
        data = target.read_bytes()
        updated = patch_source(data)
        if updated == data.replace(b"\r\n", b"\n"):
            print("Pipeline worker stack patch is already present at 32 MiB.")
            return 0
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
