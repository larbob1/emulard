# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only registration: exact prepared xasync byte hash required."""
import argparse
from pathlib import Path
from preview_hle_pool_native import preview, FIXTURE

def install(checkout):
    path = checkout / "crates/victory-hle/src/modules/xasync.rs"
    original = path.read_bytes()
    updated = preview(original, FIXTURE.read_bytes())
    path.write_bytes(updated)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    install(args.checkout)
