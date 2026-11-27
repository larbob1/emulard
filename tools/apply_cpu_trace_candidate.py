#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply only the coordinator-reviewed CPU trace hooks to a prepared source tree."""
import argparse
from pathlib import Path
from propose_cpu_trace_hooks import SOURCE_PATHS, preview

ROOT = Path(__file__).resolve().parents[1]

def apply(root):
    paths = {name: root / path for name, path in SOURCE_PATHS.items()}
    if paths["cpu_trace.rs"].exists():
        raise ValueError("CPU trace module already exists")
    files = {name: path.read_text(encoding="utf-8")
             for name, path in paths.items() if name != "cpu_trace.rs"}
    changed = preview(files,
                      (ROOT / "probes/cpu_trace_buffer.rs").read_text(encoding="utf-8"),
                      (ROOT / "probes/cpu_trace_runtime_bridge.rs").read_text(encoding="utf-8"))
    # All seven anchors must be valid before the first write. This is a
    # disposable prepared checkout, never a title directory or source branch.
    for name, source in changed.items():
        paths[name].write_text(source, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    try:
        apply(args.prepared)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"CPU trace preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
