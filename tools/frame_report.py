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
    rf"(?P<copy_mb>{NUMBER}) MB, textures (?P<texture>{NUMBER}) ms (?P<texture_mb>{NUMBER}) MB; "
    rf"(?P<gpu>{NUMBER}) on the\s+GPU; (?P<back>{NUMBER}) copying back "
    rf"(?P<back_mb>{NUMBER}) MB\), (?P<draws>{NUMBER}) draws/frame, dropped (?P<dropped>{NUMBER}) "
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
        "intervals_meeting_target_without_reported_drops": sum(row["frame"] <= 100 and row["dropped"] == 0 and row["compiling"] == 0 for row in rows),
        "median_reported_interval": med,
        "target_frame_ms": 100,
        "frame_ms_above_target": round(max(0, frame - 100), 3),
        "intervals_at_or_below_target": sum(row["frame"] <= 100 for row in rows),
        "intervals_with_dropped_draws": sum(row["dropped"] > 0 for row in rows),
        "note": "Interval medians, not per-frame percentiles; stage timings can overlap."
    }

def compare(baseline, candidate):
    """Compare matching workload interval summaries, not individual frames."""
    if not baseline["samples"] or not candidate["samples"]:
        return {"status": "insufficient samples"}
    a, b = baseline["median_reported_interval"], candidate["median_reported_interval"]
    return {
        "baseline_samples": baseline["samples"],
        "candidate_samples": candidate["samples"],
        "median_frame_ms_delta": round(b["frame"] - a["frame"], 3),
        "median_frame_speedup": round(a["frame"] / b["frame"], 3) if b["frame"] > 0 else None,
        "median_copy_back_mb_delta": round(b["back_mb"] - a["back_mb"], 3),
        "median_dropped_draws_delta": round(b["dropped"] - a["dropped"], 3),
        "candidate_clean_target_intervals": candidate["intervals_meeting_target_without_reported_drops"],
        "note": "Same scene, settings and warmup required; no reported drops does not establish correct rendering."
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--baseline", type=Path, help="optional comparison log for the same workload")
    parser.add_argument("--skip", type=int, default=0, help="ignore initial matching samples")
    args = parser.parse_args()
    if args.skip < 0:
        parser.error("--skip must be nonnegative")
    try:
        with args.log.open(encoding="utf-8", errors="replace") as handle:
            report = summarize(handle, args.skip)
        if args.baseline:
            with args.baseline.open(encoding="utf-8", errors="replace") as handle:
                report["comparison"] = compare(summarize(handle, args.skip), report)
    except OSError:
        print(json.dumps({"samples": 0, "status": "log unavailable"}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["samples"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
