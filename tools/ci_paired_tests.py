#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the shared paired-wave test/build plan on an already prepared checkout."""
import argparse
import os
from pathlib import Path
import subprocess
from build_runtime import PAIRED_WAVE_REFRESH, validate_paired

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    root = args.checkout.resolve()
    if os.name != "nt" or not (root / ".git").exists():
        parser.error("A prepared Windows checkout is required.")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if revision != PAIRED_WAVE_REFRESH:
        parser.error("Unexpected pinned revision.")
    validate_paired(root)

if __name__ == "__main__":
    main()
