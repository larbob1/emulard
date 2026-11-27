#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Attempt a Windows-target build from a prepared Linux checkout."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from build_runtime import REVISION, FXCELESS_REFRESH, PAIRED_WAVE_REFRESH

REVISIONS = frozenset((REVISION, FXCELESS_REFRESH, PAIRED_WAVE_REFRESH))
TARGET = "x86_64-pc-windows-msvc"

def build_command(root, diagnostics, jobs):
    if not 1 <= jobs <= 64:
        raise ValueError("Build jobs must be between 1 and 64.")
    profile = "diag" if diagnostics else "release"
    # A deterministic output path, even with CARGO_TARGET_DIR set.
    target_dir = root / "target"
    command = ["cargo", "xwin", "build", "--target", TARGET,
               "--target-dir", str(target_dir), "--locked", "-p", "victory",
               "--jobs", str(jobs)]
    if diagnostics:
        command.extend(["--profile", "diag", "--features", "diagnostics"])
    else:
        command.append("--release")
    return command, target_dir / TARGET / profile / "victory.exe"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--diagnostics", action="store_true", help="build the diagnostic profile instead of release")
    parser.add_argument("--jobs", type=int, default=2, help="maximum concurrent Cargo build jobs (default 2)")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error("--jobs must be between 1 and 64.")
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
        if revision not in REVISIONS:
            print("Unexpected upstream revision.")
            return 1
        # The user supplies the toolchain; no package manager or privilege
        # changes are performed here. Cargo and xwin may fetch dependencies.
        env = os.environ.copy()
        command, binary = build_command(root, args.diagnostics, args.jobs)
        subprocess.run(command, cwd=root, env=env, check=True)
        if not binary.is_file():
            print("Build ended without the expected executable.")
            return 1
        profile = "diagnostic" if args.diagnostics else "release"
        print(f"Windows-target {profile} executable built locally. Run synthetic checks next.")
        return 0
    except (OSError, subprocess.CalledProcessError):
        print("Cross-build failed. Review compiler output locally.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
