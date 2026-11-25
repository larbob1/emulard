#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Summarize known runtime diagnostics without emitting raw log content."""
import argparse
import json
from pathlib import Path
import re

from frame_report import summarize

# Fixed categories only. Never return a captured error string, shader hash,
# virtual address, local pathname or any other arbitrary text from the log.
REASONS = {
    "wave_control_flow": (
        "where not every lane runs",
        "group-wide meetings in independently branching console waves",
        "a lane mask read as data in a half-wave",
        "a lane read in a half-wave",
        "a lane write in a half-wave",
    ),
    "shared_memory_limit": ("split-wave shared memory exceeds the host limit",),
    "signed_mad_flag": ("a signed multiply-add flag",),
    "raw_addressing": ("a raw address", "global atomic", "flat memory"),
    "relative_register": ("relative VGPR", "relative register", "relative vgpr"),
}
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
BUILDER_MISSING = re.compile(r"\bmissing=(\d+)\b")
BUILDER_TOTAL = re.compile(r"\bof=(\d+)\b")
BUILDER_READY = re.compile(r"\bpipelines=(\d+)\b")
PAGES = re.compile(r"\bpages=(\d+)\b")
DIRTY = re.compile(r"\bdirty_pages=(\d+)\b")

def number(pattern, line):
    match = pattern.search(line)
    if match and len(match[1]) <= 12:
        return int(match[1])
    return None

def summarize_readiness(lines, skip=0):
    counts = dict.fromkeys((*REASONS, "other"), 0)
    builder = {"ready_reports": 0, "disabled_reports": 0,
               "last_missing": None, "last_total": None}
    memory = {"fault_reports": 0, "reported_missing_pages": 0,
              "completed_feedback_reports": 0, "reported_dirty_pages": 0,
              "directory_capacity_reports": 0}
    def observed():
        for line in lines:
            line = ANSI.sub("", line)
            if "shader does not translate; its pipelines' draws are dropped" in line:
                reason = next((k for k, values in REASONS.items()
                               if any(value in line for value in values)), "other")
                counts[reason] += 1
            if "the ray-tracing structure builder stays off:" in line:
                builder["disabled_reports"] += 1
                builder["last_missing"] = number(BUILDER_MISSING, line)
                builder["last_total"] = number(BUILDER_TOTAL, line)
            elif "the ray-tracing structure builder is turned off" in line:
                builder["disabled_reports"] += 1
            elif "the ray-tracing structure builder runs: all of its programs have host pipelines" in line:
                builder["ready_reports"] += 1
                builder["last_missing"] = 0
                builder["last_total"] = number(BUILDER_READY, line)
            if "shaders touched pages that had no copy" in line:
                memory["fault_reports"] += 1
                memory["reported_missing_pages"] += number(PAGES, line) or 0
            if "completed raw memory feedback" in line:
                memory["completed_feedback_reports"] += 1
                memory["reported_dirty_pages"] += number(DIRTY, line) or 0
            if "no number left for another copy" in line:
                memory["directory_capacity_reports"] += 1
            yield line
    frame = summarize(observed(), skip)
    return {
        "frame": frame,
        "translation_warning_counts": counts,
        "builder": builder,
        "memory": memory,
        "note": ("Counts of observed log messages, not unique shaders or proof of correctness. "
                 "Warnings may be rate-limited; missing messages are not evidence of success. "
                 "A ready builder report means pipelines exist, not that their results are valid.")
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--skip", type=int, default=0)
    args = parser.parse_args()
    if args.skip < 0:
        parser.error("--skip must be nonnegative")
    try:
        with args.log.open(encoding="utf-8", errors="replace") as handle:
            report = summarize_readiness(handle, args.skip)
    except OSError:
        print(json.dumps({"status": "log unavailable"}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
