#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the actual prepared portable copy helpers independently of D3D12."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

SECTIONS = (
    ("fn merge_piece(now:", "/// `[from, to)` without the ranges of"),
    ("fn trim_idle_pool(", "/// The unit shader writes are looked for and put back in."),
)

def extract(source):
    blocks = []
    for start, end in SECTIONS:
        if source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("Portable helper source anchor mismatch")
        a, b = source.index(start), source.index(end)
        if a >= b:
            raise ValueError("Portable helper source order mismatch")
        blocks.append(source[a:b])
    return "\n".join(blocks)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    source = args.checkout / "crates/victory-gpu/src/shadow.rs"
    try:
        helpers = extract(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="emulard-portable-") as temp:
            path = Path(temp) / "copy_helpers.rs"
            binary = Path(temp) / ("copy_helpers.exe" if os.name == "nt" else "copy_helpers")
            path.write_text(helpers, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2024", "--test", str(path), "-o", str(binary)], check=True)
            for enabled in ("0", "1"):
                print(f"Portable copy helper tests: AVX2/sparse={enabled}", flush=True)
                subprocess.run([str(binary)], env=dict(os.environ,
                    VICTORY_BACK_AVX2=enabled, VICTORY_BACK_SPARSE_MERGE=enabled), check=True)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Portable copy helper validation failed.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
