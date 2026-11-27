#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Summarize only numerical frame telemetry; never upload or echo source logs."""
import argparse
import json
from math import ceil
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

def summarize(lines, skip=0, skip_frame_batches=0):
    rows = []
    seen = 0
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
        if match:
            seen += 1
            if seen <= skip:
                continue
            row = {key: float(value) for key, value in match.groupdict().items()}
            if row["frame"] > 0:
                rows.append(row)
    actual = {
        "samples": len(individual_frames),
        "batches_skipped": min(batches_seen, skip_frame_batches),
        "batches_used": max(0, batches_seen - skip_frame_batches),
        "invalid_batches": invalid_batches,
        "frame_ms_percentiles": {f"p{p}": percentile(individual_frames, p / 100) for p in (50, 90, 95, 99)},
        "max_ms": max(individual_frames, default=None),
        "note": "Individual present-to-present durations rounded to integer milliseconds. Independent of interval warmup and drop counts; not proof of correct rendering.",
    }
    detailed = {"individual_frame_times": actual, "latest_cumulative_counters": cumulative,
                "long_frame_samples": len(remaps), "long_frame_remapping": stats(remaps),
                "alias_rate_samples": len(aliases), "alias_rates_per_second": stats(aliases),
                "reported_long_frames": {"samples": len(long_frames), "max_ms": max(long_frames, default=None),
                    "omitted_count": omitted_long, "note": "Selected slow frames only; not a full distribution."}}
    if not rows:
        return {"samples": 0, "status": "no matching positive frame-time samples", **detailed}
    med = {key: round(median(row[key] for row in rows), 3) for key in rows[0]}
    frame = med["frame"]
    return {
        "samples": len(rows),
        **detailed,
        "intervals_meeting_target_without_reported_drops": sum(row["frame"] <= 100 and row["dropped"] == 0 and row["compiling"] == 0 for row in rows),
        "median_reported_interval": med,
        "reported_interval_frame_ms_percentiles": {f"p{p}": percentile([row["frame"] for row in rows], p / 100) for p in (50, 90, 95, 99)},
        "fps_milestones": {str(fps): {"intervals": sum(row["frame"] <= 1000 / fps for row in rows),
            "without_reported_drops_or_pending": sum(row["frame"] <= 1000 / fps and row["dropped"] == 0 and row["compiling"] == 0 for row in rows)} for fps in (5, 10, 20, 30, 60)},
        "target_frame_ms": 100,
        "frame_ms_above_target": round(max(0, frame - 100), 3),
        "intervals_at_or_below_target": sum(row["frame"] <= 100 for row in rows),
        "intervals_with_dropped_draws": sum(row["dropped"] > 0 for row in rows),
        "note": "Interval averages, not per-frame percentiles; stage timings can overlap. Visual correctness must be verified separately."
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
    parser.add_argument("--skip", type=int, default=0, help="ignore initial matching FPS intervals")
    parser.add_argument("--skip-frame-batches", type=int, default=0, help="independently ignore initial detailed frame batches")
    args = parser.parse_args()
    if args.skip < 0 or args.skip_frame_batches < 0:
        parser.error("warmup counts must be nonnegative")
    try:
        with args.log.open(encoding="utf-8", errors="replace") as handle:
            report = summarize(handle, args.skip, args.skip_frame_batches)
        if args.baseline:
            with args.baseline.open(encoding="utf-8", errors="replace") as handle:
                report["comparison"] = compare(summarize(handle, args.skip, args.skip_frame_batches), report)
    except OSError:
        print(json.dumps({"samples": 0, "status": "log unavailable"}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["samples"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
