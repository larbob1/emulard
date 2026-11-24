#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile a source-only candidate on a Windows CI host."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent

def run_stage(label, args, cwd):
    # Do not publish external source excerpts, local paths or raw tool logs.
    # Report only a stage name, exit status, and structured Rust error codes.
    print(f"Starting: {label}", flush=True)
    with tempfile.TemporaryFile(mode="w+b") as output:
        result = subprocess.run(args, cwd=cwd, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            output.seek(0)
            codes = set()
            for line in output:
                codes.update(re.findall(rb"error\[(E[0-9]{4})\]", line))
            if codes:
                print("Rust diagnostics: " + ", ".join(code.decode("ascii") for code in sorted(codes)))
            print(f"Failed: {label} (exit {result.returncode})", flush=True)
            raise SystemExit(1)
    print(f"Passed: {label}", flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lighting-memory", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Windows build host required.")
    try:
        with tempfile.TemporaryDirectory(prefix="emulard-ci-") as directory:
            target = Path(directory) / "runtime"
            prepare = [sys.executable, str(ROOT / "tools" / "build_runtime.py"), str(target)]
            if args.lighting_memory:
                prepare.append("--lighting-memory")
            run_stage("Pinned source preparation", prepare, ROOT)
            run_stage("Pinned Rust toolchain", ["rustup", "toolchain", "install"], target)
            suites = [
                ("Memory scheduling", "victory-gpu", "raw_copy_progress_tests"),
                ("Query bounds", "victory-gpu", "query_range_tests"),
                ("Wave retry policy", "victory-shader", "wave_retry_policy_tests"),
                ("Ray intersection reference", "victory-shader", "bvh::tests::"),
            ]
            for label, package, name in suites:
                run_stage(label, ["cargo", "test", "--locked", "-p", package, "--lib", name], target)
            run_stage("Release runtime compilation", ["cargo", "build", "--locked", "--release", "-p", "victory"], target)
            run_stage("Diagnostics type check", ["cargo", "check", "--locked", "-p", "victory", "--features", "diagnostics"], target)
            print("Compile and targeted test checks completed. No runtime execution was attempted.", flush=True)
    except OSError:
        print("CI preparation or cleanup failed.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
