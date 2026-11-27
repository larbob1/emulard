#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile actual prepared, platform-independent window geometry and tests."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from build_runtime import test_result_counts

def unique(pattern, source):
    matches = re.findall(pattern, source, flags=re.MULTILINE | re.DOTALL)
    if len(matches) != 1:
        raise ValueError("missing or ambiguous portable window source anchor")
    return matches[0]

def portable_source(source):
    constants = [unique(r"^const " + name + r": u64 = [^\n;]+;", source)
                 for name in ("WINDOW", "TAIL_STEP")]
    helpers = [unique(r"^fn " + name + r"\([^\n]*\{\n.*?^\}", source)
               for name in ("grid", "window_of", "holder", "cover", "tail_of", "longest_tail")]
    tests = unique(r"^mod window_tests \{\n.*?^\}", source)
    return "\n\n".join(constants + helpers + [tests]) + "\n"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    try:
        shadow = (args.prepared / "crates/victory-gpu/src/shadow.rs").read_text(encoding="utf-8")
        source = portable_source(shadow)
        with tempfile.TemporaryDirectory(prefix="window-geometry-") as tmp:
            rust = Path(tmp) / "window.rs"
            binary = Path(tmp) / "window-tests"
            rust.write_text(source, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2024", "--test", str(rust), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(result.stdout, end="")
            result.check_returncode()
            if test_result_counts(result.stdout) != [(8, 0)]:
                raise ValueError("expected exactly eight passing window cases")
        print("Portable window geometry: passed=8 failed=0")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Portable window geometry validation failed")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
