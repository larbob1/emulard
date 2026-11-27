#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Local paired benchmark aggregation; never publishes raw logs or paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from statistics import median
from math import isfinite
from frame_report import compare, summarize

def aggregate(pairs, visible=False):
    results = []
    for baseline, candidate in pairs:
        comparison = compare(baseline, candidate)
        a, b = (report.get("median_reported_interval") for report in (baseline, candidate))
        interval_usable = comparison.get("interval_comparison_usable", False)
        frame_usable = comparison.get("individual_comparison_usable", False)
        af, bf = (report["individual_frame_times"] for report in (baseline, candidate))
        ad = baseline.get("intervals_with_dropped_draws")
        bd = candidate.get("intervals_with_dropped_draws")
        results.append({
            "baseline_ms": a["frame"] if a else None,
            "candidate_ms": b["frame"] if b else None,
            "speedup": a["frame"] / b["frame"] if interval_usable else None,
            "approx_present_fps_ratio": (
                bf["samples"] * af["duration_ms_rounded_samples"]
                / (af["samples"] * bf["duration_ms_rounded_samples"]) if frame_usable else None),
            "baseline_drop_intervals": ad,
            "candidate_drop_intervals": bd,
            "baseline_shader_translation_drop_warning_lines": baseline.get("shader_translation_drop_warning_lines"),
            "candidate_shader_translation_drop_warning_lines": candidate.get("shader_translation_drop_warning_lines"),
            "baseline_drop_interval_fraction": ad / baseline["samples"] if baseline["samples"] else None,
            "candidate_drop_interval_fraction": bd / candidate["samples"] if candidate["samples"] else None,
            "baseline_intervals": baseline["samples"],
            "candidate_intervals": candidate["samples"],
            "baseline_interval_quality": baseline.get("interval_sample_quality"),
            "candidate_interval_quality": candidate.get("interval_sample_quality"),
            "baseline_individual": af,
            "candidate_individual": bf,
            "baseline_latest_cumulative_counters": baseline.get("latest_cumulative_counters", {}),
            "candidate_latest_cumulative_counters": candidate.get("latest_cumulative_counters", {}),
            "baseline_cumulative_counter_observations": baseline.get("cumulative_counter_observations", {}),
            "candidate_cumulative_counter_observations": candidate.get("cumulative_counter_observations", {}),
            "baseline_dirty_observation": baseline.get("dirty_observation"),
            "candidate_dirty_observation": candidate.get("dirty_observation"),
            "baseline_critical_path_evidence": baseline.get("critical_path_evidence"),
            "candidate_critical_path_evidence": candidate.get("critical_path_evidence"),
            "interval_comparison_usable": interval_usable,
            "individual_comparison_usable": frame_usable,
        })
    if not results:
        raise ValueError("At least one matched pair is required.")
    intervals = [r for r in results if r["interval_comparison_usable"]]
    frames = [r for r in results if r["individual_comparison_usable"]]
    if not intervals and not frames:
        raise ValueError("No pair has a usable shared sample population.")
    return {
        "pairs": len(results),
        "runs": results,
        "usable_interval_pairs": len(intervals),
        "usable_individual_pairs": len(frames),
        "incomplete_pairs": sum(not (r["interval_comparison_usable"] and r["individual_comparison_usable"]) for r in results),
        "median_paired_speedup": round(median(r["speedup"] for r in intervals), 4) if intervals else None,
        "median_paired_approx_present_fps_ratio": round(median(r["approx_present_fps_ratio"] for r in frames), 4) if frames else None,
        "candidate_faster_pairs": sum(r["speedup"] > 1 for r in intervals),
        "candidate_pairs_with_reported_drops": sum((r["candidate_drop_intervals"] or 0) > 0 for r in results),
        "candidate_pairs_with_unknown_drops": sum(r["candidate_drop_intervals"] is None for r in results),
        "candidate_pairs_with_shader_translation_warnings": sum(
            (r["candidate_shader_translation_drop_warning_lines"] or 0) > 0 for r in results),
        "candidate_pairs_with_unknown_shader_warning_counts": sum(
            r["candidate_shader_translation_drop_warning_lines"] is None for r in results),
        "at_least_three_pairs": len(results) >= 3,
        "at_least_three_usable_interval_pairs": len(intervals) >= 3,
        "at_least_three_usable_individual_pairs": len(frames) >= 3,
        "operator_reported_visible_scene": visible,
        "note": "Operator must match scene/settings/warmup and independent runs. Distinct log contents do not prove independent trials or matched workloads. Ratios exclude unusable populations, not whole runs; counts expose missing evidence. Interval averages are not individual frames; rounded present rates are not visible gameplay FPS. Visibility is self-reported. Shader warning lines cover the entire supplied input including warmup; no known warning is not proof of rendering correctness. Dirty observation is diagnostic-only; no speedup ratio certifies an instrumented trial. This report is not a release gate.",
    }

def read_distinct_log(path, seen_paths, seen_contents, skip, skip_frame_batches, target_fps):
    resolved = path.resolve()
    if resolved in seen_paths:
        raise ValueError("repeated_input_path")
    digest = hashlib.sha256()
    with path.open(encoding="utf-8", errors="replace", newline=None) as handle:
        before = os.fstat(handle.fileno())

        def observed_lines():
            for line in handle:
                # Hash exactly the text the parser consumes. Universal newlines
                # make CRLF/LF copies equivalent; normalize final newline too.
                digest.update(line.rstrip("\n").encode("utf-8"))
                digest.update(b"\n")
                yield line

        report = summarize(observed_lines(), skip, skip_frame_batches, target_fps)
        after = os.fstat(handle.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("input_changed_during_read")
    fingerprint = digest.digest()
    if fingerprint in seen_contents:
        raise ValueError("repeated_log_content")
    seen_paths.add(resolved)
    seen_contents.add(fingerprint)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", action="append", nargs=2, type=Path, required=True,
                        metavar=("BASELINE_LOG", "CANDIDATE_LOG"))
    parser.add_argument("--skip", type=int, default=5)
    parser.add_argument("--skip-frame-batches", type=int, default=0, help="independent detailed-batch warmup")
    parser.add_argument("--target-fps", type=float, default=30)
    parser.add_argument("--visible-scene-confirmed", action="store_true",
                        help="operator confirms full scene visible in every run")
    args = parser.parse_args()
    if args.skip < 0 or args.skip_frame_batches < 0:
        parser.error("warmup counts must be nonnegative")
    if not isfinite(args.target_fps) or not 0.001 <= args.target_fps <= 10000:
        parser.error("--target-fps must be finite and between 0.001 and 10000")
    try:
        pairs = []
        seen_paths = set()
        seen_contents = set()
        for paths in args.pair:
            pairs.append([read_distinct_log(path, seen_paths, seen_contents, args.skip,
                                          args.skip_frame_batches, args.target_fps) for path in paths])
        result = aggregate(pairs, args.visible_scene_confirmed)
        result["target_fps"] = args.target_fps
        result["warmup_intervals"] = args.skip
        result["warmup_frame_batches"] = args.skip_frame_batches
        result["distinct_normalized_log_contents"] = len(seen_contents)
        result["independent_trials_verified"] = False
        result["matched_workload_verified"] = False
    except (OSError, ValueError) as exc:
        reason = str(exc)
        allowed = {"repeated_input_path", "repeated_log_content", "input_changed_during_read"}
        print(json.dumps({"status": "unavailable or insufficient benchmark data",
                          "reason": reason if reason in allowed else "invalid_or_unavailable"}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
