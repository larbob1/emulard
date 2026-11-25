#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run trusted local smoke probes and optional runtime version check."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

def is_x64_pe(path):
    try:
        with path.open("rb") as f:
            header = f.read(64)
            if len(header) != 64 or header[:2] != b"MZ":
                return False
            offset = struct.unpack_from("<I", header, 60)[0]
            f.seek(offset)
            pe = f.read(26)
            return (len(pe) == 26 and pe[:4] == b"PE\0\0"
                    and struct.unpack_from("<H", pe, 4)[0] == 0x8664
                    and struct.unpack_from("<H", pe, 24)[0] == 0x20B)
    except OSError:
        return False

def run_probe(wine, path, extra, timeout):
    if not is_x64_pe(path):
        return "missing-or-invalid-x64-pe"
    try:
        result = subprocess.run([wine, str(path.resolve()), *extra],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=timeout,
                                check=False)
        return "passed" if result.returncode == 0 else f"exit-{result.returncode}"
    except subprocess.TimeoutExpired:
        return "timed-out"
    except OSError:
        return "execution-failed"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe_dir", type=Path, help="directory containing trusted synthetic probes")
    parser.add_argument("--runtime", type=Path, help="locally built executable; runs only --version")
    parser.add_argument("--wine", default="wine", help="trusted Wine executable or executable path")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("Use on a Linux host.")
    wine = shutil.which(args.wine)
    if not wine:
        print(json.dumps({"wine": "not-found", "status": "blocked"}))
        return 1
    report = {"abi": run_probe(wine, args.probe_dir / "abi_smoke.exe", [], 30)}
    # Do not advance to graphics or the runtime if basic execution failed.
    if report["abi"] == "passed":
        report["graphics"] = run_probe(wine, args.probe_dir / "graphics_caps.exe", [], 60)
    else:
        report["graphics"] = "not-run"
    if args.runtime and report["graphics"] == "passed":
        report["runtime_version"] = run_probe(wine, args.runtime, ["--version"], 30)
    else:
        report["runtime_version"] = "not-run"
    report["status"] = ("smoke-checks-passed" if all(report[k] == "passed"
                        for k in ("abi", "graphics", "runtime_version")) else "incomplete")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "smoke-checks-passed" else 1

if __name__ == "__main__":
    raise SystemExit(main())
