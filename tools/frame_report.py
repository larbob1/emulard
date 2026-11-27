#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Summarize only numerical frame telemetry; never upload or echo source logs."""
import argparse
import json
from math import ceil, isfinite
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

# Long-frame diagnostics are a separate population from interval summaries.
# Worker totals overlap; never present them as percentages of wall time.
REMAP_PATTERN = re.compile(
    rf"remapping: (?P<calls>{NUMBER}) calls (?P<total_ms>{NUMBER}) ms "
    rf"\((?P<reader_wait_ms>{NUMBER}) waiting for readers; of it the system's "
    rf"unmapping (?P<unmap_ms>{NUMBER}), its mapping (?P<map_ms>{NUMBER}), "
    rf"committing (?P<commit_ms>{NUMBER}), our own notes of the change "
    rf"(?P<notes_ms>{NUMBER}); (?P<views_cut>{NUMBER}) views cut, "
    rf"(?P<remapped_mb>{NUMBER}) MB of them mapped again"
    rf"(?:; (?P<reused>{NUMBER}) placeholders reused, (?P<fallbacks>{NUMBER}) reuse fallbacks)?\)"
)
REFRESH_RE = re.compile(rf"textures: refresh (?P<refresh_ms>{NUMBER}) ms \((?P<refresh_wait_ms>{NUMBER}) waiting for memory to hold still\)")
ALIAS_RE = re.compile(
    rf"page mappings of the title's queues per second: (?P<calls>{NUMBER}) calls for "
    rf"(?P<pages>{NUMBER}) pages, (?P<same>{NUMBER}) of them as they were, "
    rf"(?P<views>{NUMBER}) views mapped, (?P<ms>{NUMBER}) ms"
)

def numeric_match(pattern, line):
    match = pattern.search(line)
    return {k: float(v) for k, v in match.groupdict().items() if v is not None} if match else {}

def stats(rows):
    return {key: {"median": round(median(values), 3), "max": max(values), "samples": len(values)}
            for key in sorted({key for row in rows for key in row})
            if (values := [row[key] for row in rows if key in row])}


LONG_FRAME = re.compile(rf"\blong frame [0-9]+ at {NUMBER} s: (?P<ms>{NUMBER}) ms \|")
OMITTED_LONG = re.compile(r"\blong frames: (?P<count>[0-9]+) more in this reading are not listed")

# The upstream framelog emits every rounded frame duration in a batch.
# Match the complete numeric payload and validate its declared count.
FRAME_BATCH = re.compile(
    rf"\bframe times: (?P<count>[0-9]+) frames in {NUMBER} s: shortest {NUMBER} ms, "
    rf"median {NUMBER}, longest {NUMBER}; [0-9]+ long \(over {NUMBER} ms, "
    rf"the usual frame of the last [0-9]+ being {NUMBER}\); each: (?P<each>[0-9 ]+)\s*$"
)

def frame_batch(line):
    match = FRAME_BATCH.search(line)
    if not match:
        return None
    values = [int(v) for v in match["each"].split()]
    if not values or len(values) != int(match["count"]):
        return None
    return values

def percentile(values, fraction):
    """Nearest rank, on the supplied sample population only."""
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * fraction) - 1)] if ordered else None

# Cumulative power-of-two counters, not per-frame samples. Keep only
# numeric allowlisted fields; output the latest observed record, not sums.
COUNTERS = {
    "mapping diff totals": ("calls", "saved", "mapped", "scatter"),
    "texture short-lock totals": ("calls", "bytes", "copy_us", "unlocked_us", "retries"),
    "unchanged physical mapping requests skipped": ("count",),
    "mapping diff run totals": ("runs", "pages"),
    "texture view estimate hits": ("hits",),
    "alias direct run totals": ("attempts", "hits"),
}
def update_counters(latest, line):
    for message, fields in COUNTERS.items():
        if message not in line:
            continue
        values = {}
        for field in fields:
            match = re.search(rf"\b{field}=([0-9]+)\b", line)
            if match:
                values[field] = int(match[1])
        if len(values) == len(fields):
            latest[message] = values

def summarize(lines, skip=0, skip_frame_batches=0, target_fps=10):
    if not isfinite(target_fps) or not 0.001 <= target_fps <= 10000:
        raise ValueError("target_fps must be finite and between 0.001 and 10000")
    if skip < 0 or skip_frame_batches < 0:
        raise ValueError("warmup counts must be nonnegative")
    target_ms = 1000 / target_fps
    rows = []
    seen = invalid_intervals = skipped_intervals = 0
    remaps, aliases, long_frames = [], [], []
    omitted_long = 0
    cumulative = {}
    individual_frames = []
    batches_seen = invalid_batches = 0
    for line in lines:
        update_counters(cumulative, line)
        if "frame times:" in line:
            batch = frame_batch(line)
            if batch is None:
                invalid_batches += 1
            else:
                batches_seen += 1
                if batches_seen > skip_frame_batches:
                    individual_frames.extend(batch)
        if seen >= skip:
            long = LONG_FRAME.search(line)
            if long:
                long_frames.append(float(long["ms"]))
            omitted = OMITTED_LONG.search(line)
            if omitted:
                omitted_long += int(omitted["count"])
            remap = numeric_match(REMAP_PATTERN, line)
            if remap:
                remap.update(numeric_match(REFRESH_RE, line))
                remaps.append(remap)
            alias = numeric_match(ALIAS_RE, line)
            if alias:
                aliases.append(alias)
        match = PATTERN.search(line)
        if match or re.search(r"\bfps,\s.*\bms/frame\b", line):
            seen += 1
            row = {key: float(value) for key, value in match.groupdict().items()} if match else {}
            valid = bool(row) and row["frame"] > 0 and all(isfinite(v) for v in row.values())
            if seen <= skip:
                skipped_intervals += 1
            elif valid:
                rows.append(row)
            else:
                invalid_intervals += 1
    actual = {
        "samples": len(individual_frames),
        "duration_ms_rounded_samples": sum(individual_frames),
        "approx_present_fps": round(1000 * len(individual_frames) / sum(individual_frames), 3) if sum(individual_frames) else None,
        "frames_within_target_ms": sum(ms <= target_ms for ms in individual_frames),
        "batches_skipped": min(batches_seen, skip_frame_batches),
        "batches_used": max(0, batches_seen - skip_frame_batches),
        "invalid_batches": invalid_batches,
        "frame_ms_percentiles": {f"p{p}": percentile(individual_frames, p / 100) for p in (50, 90, 95, 99)},
        "max_ms": max(individual_frames, default=None),
        "note": "Individual present-to-present durations rounded to integer milliseconds. Approximate present FPS is sample count divided by the sum of rounded durations, not verified visible gameplay FPS. Independent of interval warmup and drop counts.",
    }
    detailed = {"individual_frame_times": actual, "latest_cumulative_counters": cumulative,
                "interval_sample_quality": {"seen": seen, "skipped": skipped_intervals,
                    "invalid_after_warmup": invalid_intervals, "used": len(rows)},
                "long_frame_samples": len(remaps), "long_frame_remapping": stats(remaps),
                "alias_rate_samples": len(aliases), "alias_rates_per_second": stats(aliases),
                "reported_long_frames": {"samples": len(long_frames), "max_ms": max(long_frames, default=None),
                    "omitted_count": omitted_long, "note": "Selected slow frames only; not a full distribution."}}
    if not rows:
        return {"samples": 0, "status": "no matching positive frame-time samples", **detailed}
    med = {key: round(median(row[key] for row in rows), 3) for key in rows[0]}
    # Do not round a positive sub-millisecond median to zero before comparison.
    med["frame"] = median(row["frame"] for row in rows)
    frame = med["frame"]
    return {
        "samples": len(rows),
        **detailed,
        "intervals_meeting_target_without_reported_drops": sum(row["frame"] <= target_ms and row["dropped"] == 0 and row["compiling"] == 0 for row in rows),
        "median_reported_interval": med,
        "reported_interval_frame_ms_percentiles": {f"p{p}": percentile([row["frame"] for row in rows], p / 100) for p in (50, 90, 95, 99)},
        "fps_milestones": {str(fps): {"intervals": sum(row["frame"] <= 1000 / fps for row in rows),
            "without_reported_drops_or_pending": sum(row["frame"] <= 1000 / fps and row["dropped"] == 0 and row["compiling"] == 0 for row in rows)} for fps in (5, 10, 20, 30, 60)},
        "target_fps": target_fps,
        "target_frame_ms": round(target_ms, 6),
        "frame_ms_above_target": round(max(0, frame - target_ms), 3),
        "intervals_at_or_below_target": sum(row["frame"] <= target_ms for row in rows),
        "intervals_with_dropped_draws": sum(row["dropped"] > 0 for row in rows),
        "note": "Interval averages, not per-frame percentiles; stage timings can overlap. Visual correctness must be verified separately."
    }

def compare(baseline, candidate):
    """Compare independent interval and individual-frame populations."""
    a, b = (report.get("median_reported_interval") for report in (baseline, candidate))
    base_frames, cand_frames = (report["individual_frame_times"] for report in (baseline, candidate))
    intervals = bool(a and b)
    frame_samples = bool(base_frames["samples"] and cand_frames["samples"]
                         and base_frames["duration_ms_rounded_samples"]
                         and cand_frames["duration_ms_rounded_samples"])
    if not intervals and not frame_samples:
        return {"status": "insufficient samples"}
    interval_clean = intervals and not any(
        report.get("interval_sample_quality", {}).get("invalid_after_warmup", 0)
        for report in (baseline, candidate))
    frame_clean = frame_samples and not any(
        frames["invalid_batches"] for frames in (base_frames, cand_frames))
    ratio = (cand_frames["samples"] * base_frames["duration_ms_rounded_samples"]
             / (base_frames["samples"] * cand_frames["duration_ms_rounded_samples"])
             if frame_clean else None)
    return {
        "status": "both populations available" if interval_clean and frame_clean else "partial samples",
        "baseline_approx_present_fps": base_frames["approx_present_fps"],
        "candidate_approx_present_fps": cand_frames["approx_present_fps"],
        "approx_present_fps_ratio": round(ratio, 3) if ratio is not None else None,
        "baseline_individual_frame_samples": base_frames["samples"],
        "candidate_individual_frame_samples": cand_frames["samples"],
        "baseline_invalid_frame_batches": base_frames["invalid_batches"],
        "candidate_invalid_frame_batches": cand_frames["invalid_batches"],
        "baseline_frame_ms_percentiles": base_frames["frame_ms_percentiles"],
        "candidate_frame_ms_percentiles": cand_frames["frame_ms_percentiles"],
        "baseline_samples": baseline["samples"],
        "candidate_samples": candidate["samples"],
        "interval_comparison_usable": interval_clean,
        "individual_comparison_usable": frame_clean,
        "median_frame_ms_delta": round(b["frame"] - a["frame"], 3) if interval_clean else None,
        "median_frame_speedup": round(a["frame"] / b["frame"], 3) if interval_clean else None,
        "median_copy_back_mb_delta": round(b["back_mb"] - a["back_mb"], 3) if interval_clean else None,
        "median_dropped_draws_delta": round(b["dropped"] - a["dropped"], 3) if interval_clean else None,
        "candidate_clean_target_intervals": candidate.get("intervals_meeting_target_without_reported_drops"),
        "note": "Same scene, settings and warmup required; missing or malformed populations are not zero. Individual durations are rounded. No reported drops does not establish correct rendering."
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--baseline", type=Path, help="optional comparison log for the same workload")
    parser.add_argument("--skip", type=int, default=0, help="ignore initial matching FPS intervals")
    parser.add_argument("--skip-frame-batches", type=int, default=0, help="independently ignore initial detailed frame batches")
    parser.add_argument("--target-fps", type=float, default=10, help="frame budget target (use 30 for the roadmap goal)")
    args = parser.parse_args()
    if not isfinite(args.target_fps) or not 0.001 <= args.target_fps <= 10000:
        parser.error("--target-fps must be finite and between 0.001 and 10000")
    if args.skip < 0 or args.skip_frame_batches < 0:
        parser.error("warmup counts must be nonnegative")
    try:
        with args.log.open(encoding="utf-8", errors="replace") as handle:
            report = summarize(handle, args.skip, args.skip_frame_batches, args.target_fps)
        if args.baseline:
            with args.baseline.open(encoding="utf-8", errors="replace") as handle:
                report["comparison"] = compare(summarize(handle, args.skip, args.skip_frame_batches, args.target_fps), report)
    except OSError:
        print(json.dumps({"samples": 0, "status": "log unavailable"}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["samples"] or report["individual_frame_times"]["samples"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
