#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Attempt a Windows-target build from a prepared Linux checkout."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

REVISION = "2119b0e44c53aa9648307b0c5c73590290305b1f"
TARGET = "x86_64-pc-windows-msvc"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    root = args.checkout.resolve()
    if not sys.platform.startswith("linux"):
        parser.error("This helper is for a Linux build host.")
    if not (root / ".git").exists() or not (root / "Cargo.lock").is_file():
        parser.error("Prepare a separate runtime checkout first.")
    for tool in ("git", "cargo", "cargo-xwin", "clang", "lld"):
        if not shutil.which(tool):
            print(f"Missing prerequisite: {tool}")
            return 1
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                           text=True, stderr=subprocess.DEVNULL).strip()
        if revision != REVISION:
            print("Unexpected upstream revision.")
            return 1
        # The user supplies the toolchain; no package manager or privilege
        # changes are performed here. Cargo and xwin may fetch dependencies.
        env = os.environ.copy()
        subprocess.run(["cargo", "xwin", "build", "--target", TARGET,
                        "--release", "--locked", "-p", "victory"],
                       cwd=root, env=env, check=True)
        binary = root / "target" / TARGET / "release" / "victory.exe"
        if not binary.is_file():
            print("Build ended without the expected executable.")
            return 1
        print("Windows-target executable built locally. Run synthetic checks next.")
        return 0
    except (OSError, subprocess.CalledProcessError):
        print("Cross-build failed. Review compiler output locally.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
