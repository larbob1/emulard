#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Summarize only numerical frame telemetry; never upload or echo source logs."""
import argparse
import json
from pathlib import Path
import re
from statistics import median

NUMBER = r"[0-9]+(?:\.[0-9]+)?"
PATTERN = re.compile(
    rf"(?P<fps>{NUMBER}) fps, (?P<frame>{NUMBER}) ms/frame "
    rf"\((?P<prepare>{NUMBER}) preparing: copies (?P<copy>{NUMBER}) ms "
    rf"{NUMBER} MB, textures (?P<texture>{NUMBER}) ms {NUMBER} MB; "
    rf"(?P<gpu>{NUMBER}) on the\s+GPU; (?P<back>{NUMBER}) copying back "
    rf"{NUMBER} MB\), {NUMBER} draws/frame, dropped (?P<dropped>{NUMBER}) "
    rf"without a host pipeline \((?P<compiling>[0-9]+) being made\)"
)

def summarize(lines, skip=0):
    rows = []
    seen = 0
    for line in lines:
        match = PATTERN.search(line)
        if match:
            seen += 1
            if seen <= skip:
                continue
            row = {key: float(value) for key, value in match.groupdict().items()}
            if row["frame"] > 0:
                rows.append(row)
    if not rows:
        return {"samples": 0, "status": "no matching positive frame-time samples"}
    med = {key: round(median(row[key] for row in rows), 3) for key in rows[0]}
    frame = med["frame"]
    return {
        "samples": len(rows),
        "median_reported_interval": med,
        "target_frame_ms": 100,
        "frame_ms_above_target": round(max(0, frame - 100), 3),
        "intervals_at_or_below_target": sum(row["frame"] <= 100 for row in rows),
        "intervals_with_dropped_draws": sum(row["dropped"] > 0 for row in rows),
        "note": "Interval medians, not per-frame percentiles; stage timings can overlap."
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--skip", type=int, default=0, help="ignore initial matching samples")
    args = parser.parse_args()
    if args.skip < 0:
        parser.error("--skip must be nonnegative")
    try:
        with args.log.open(encoding="utf-8", errors="replace") as handle:
            report = summarize(handle, args.skip)
    except OSError:
        print(json.dumps({"samples": 0, "status": "log unavailable"}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["samples"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
