#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Local paired benchmark aggregation; never publishes raw logs or paths."""
import argparse
import json
from pathlib import Path
from statistics import median
from frame_report import summarize

def aggregate(pairs, visible=False):
    results = []
    for baseline, candidate in pairs:
        if not baseline["samples"] or not candidate["samples"]:
            raise ValueError("Every pair must contain positive frame-time intervals.")
        a = baseline["median_reported_interval"]
        b = candidate["median_reported_interval"]
        results.append({
            "baseline_ms": a["frame"],
            "candidate_ms": b["frame"],
            "speedup": a["frame"] / b["frame"],
            "baseline_drop_intervals": baseline["intervals_with_dropped_draws"],
            "candidate_drop_intervals": candidate["intervals_with_dropped_draws"],
            "baseline_intervals": baseline["samples"],
            "candidate_intervals": candidate["samples"],
        })
    if not results:
        raise ValueError("At least one matched pair is required.")
    return {
        "pairs": len(results),
        "runs": results,
        "median_paired_speedup": round(median(r["speedup"] for r in results), 4),
        "candidate_faster_pairs": sum(r["speedup"] > 1 for r in results),
        "candidate_pairs_with_reported_drops": sum(r["candidate_drop_intervals"] > 0 for r in results),
        "at_least_three_pairs": len(results) >= 3,
        "operator_reported_visible_scene": visible,
        "note": "Operator must match scene/settings/warmup. Interval averages are not individual frames. Visibility is self-reported, not independently verified. This report is not a release gate.",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", action="append", nargs=2, type=Path, required=True,
                        metavar=("BASELINE_LOG", "CANDIDATE_LOG"))
    parser.add_argument("--skip", type=int, default=5)
    parser.add_argument("--visible-scene-confirmed", action="store_true",
                        help="operator confirms full scene visible in every run")
    args = parser.parse_args()
    if args.skip < 0:
        parser.error("--skip must be nonnegative")
    try:
        pairs = []
        for paths in args.pair:
            reports = []
            for path in paths:
                with path.open(encoding="utf-8", errors="replace") as handle:
                    reports.append(summarize(handle, args.skip))
            pairs.append(reports)
        result = aggregate(pairs, args.visible_scene_confirmed)
    except (OSError, ValueError):
        print(json.dumps({"status": "unavailable or insufficient benchmark data"}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
