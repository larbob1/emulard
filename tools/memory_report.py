#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only numeric memory observations from a single operator-selected log phase."""
import argparse
import json
from pathlib import Path
import re

# Exact pinned copystat.rs::log_memory messages. MB in these messages is
# rounded MiB (bytes / 2**20), not decimal MB or measured physical residency.
# Each group is independent, including when adjacent in the log.
def schema(marker, body, names, cumulative=()):
    pattern = re.escape(marker + body).replace(r"\#", r"([0-9]{1,20})")
    # Whitespace in Rust continued strings and log formatters may differ.
    pattern = re.sub(r"(?:\\ )+", lambda _: r"\s+", pattern)
    return marker, re.compile(pattern + r"\s*$"), names.split(), set(cumulative)


SCHEMAS = {
    "memory": schema(
        "memory:",
        " # MB private (# MB of it in memory; the PC has # MB free and # MB left to commit); host copies of title memory: # alive # MB, of them # windows outside buffers # MB; snapshot buffers kept: # reserving # MB; staging of textures: # alive # MB, # kept by their texture; host textures: # alive # MB, # placed in title memory; made so far: # upload buffers # MB, # shared buffers # MB, # card buffers # MB",
        "private_mib working_set_mib system_free_mib system_commit_left_mib host_copies host_copy_mib windows window_mib snapshots snapshot_reserved_mib texture_staging texture_staging_mib staging_kept_by_texture host_textures host_texture_mib placed_textures upload_made upload_made_mib shared_made shared_made_mib card_made card_made_mib",
        ("upload_made", "upload_made_mib", "shared_made", "shared_made_mib", "card_made", "card_made_mib")),
    "holders": schema(
        "memory, what holds it:",
        " # host lists alive; their scratch memory: # chunks # MB, of them # chunks # MB spare (# taken from the spare ones so far); their other upload buffers: # alive # MB; windows outside buffers (grid # KiB): # MB of their pages ever copied, # shown by descriptor slots # MB, # held by lists or the pass over the heap # MB, # asked for without a length # MB; buffer views of the heap whose slot showed another copy than the one brought up to date: #; distinct views kept: # (# free) # MB; our own allocations: # MB in # blocks (under 4 KiB # MB in #, to 64 KiB # MB in #, to 1 MiB # MB in #, larger # MB in #)",
        "host_lists scratch_chunks scratch_mib spare_chunks spare_mib spare_reused other_uploads other_upload_mib window_grid_kib window_pages_ever_copied_mib windows_in_slots windows_in_slots_mib windows_in_lists windows_in_lists_mib windows_unknown_length windows_unknown_length_mib heap_views_elsewhere distinct_views free_views views_mib own_mib own_blocks small_mib small_blocks medium_mib medium_blocks large_mib large_blocks huge_mib huge_blocks",
        ("spare_reused",)),
    "coverage": schema(
        "memory, windows:",
        " the # MB of windows lie over # MB of title memory (the rest is memory that is in more than one window, and is copied once for each); host lists never reset since they were made: #",
        "window_mib title_window_coverage_mib lists_never_reset"),
    "sweep": schema(
        "memory let go since the start:",
        " # windows outside buffers # MB, # staging buffers # MB; of the windows alive, # MB lie between the lowest and highest address asked for in each",
        "windows_released windows_released_mib staging_released staging_released_mib window_asked_span_mib",
        ("windows_released", "windows_released_mib", "staging_released", "staging_released_mib")),
    "shader_cache": schema(
        "memory kept beside the lines below:",
        " # shader containers # MB, # translations # MB; the pipeline library's file # MB (its last save wrote # MB)",
        "shader_containers shader_container_mib translations translation_mib pipeline_file_mib last_save_mib"),
}
MAX_U64 = 2**64 - 1


def summarize(lines):
    groups = {name: {"valid_records": 0, "invalid_records": 0,
                     "descending_cumulative_records": 0, "metrics": {}}
              for name in SCHEMAS}
    observed_grids = set()
    for ordinal, line in enumerate(lines, 1):
        for name, (marker, pattern, fields, cumulative) in SCHEMAS.items():
            # Prefix may contain a timestamp and logger target; never export it.
            starts = list(re.finditer(r"(?<!\S)" + re.escape(marker), line))
            if not starts:
                continue
            # The primary line itself contains "title memory:" later;
            # distinguish the leading private-memory signature before counting.
            if name == "memory":
                starts = [m for m in starts if re.match(
                    r"memory:\s+\S+\s+MB private", line[m.start():])]
                if not starts:
                    continue
            row = groups[name]
            match = pattern.fullmatch(line[starts[0].start():]) if len(starts) == 1 else None
            if match is None:
                row["invalid_records"] += 1
                continue
            values = dict(zip(fields, map(int, match.groups())))
            if len(values) != len(fields) or any(v > MAX_U64 for v in values.values()):
                row["invalid_records"] += 1
                continue
            if name == "holders":
                grid = values["window_grid_kib"]
                if grid not in (64, 128, 256, 512, 1024, 2048, 4096):
                    row["invalid_records"] += 1
                    continue
                observed_grids.add(grid)
            row["valid_records"] += 1
            metrics = row["metrics"]
            if any(k in metrics and values[k] < metrics[k]["last"] for k in cumulative):
                row["descending_cumulative_records"] += 1
            for key, value in values.items():
                entry = metrics.setdefault(key, {"first": value, "first_line": ordinal,
                                                  "min": value, "max": value})
                entry.update(last=value, last_line=ordinal,
                             min=min(entry["min"], value), max=max(entry["max"], value),
                             endpoint_change=value-entry["first"])
            break
    return {
        "groups": groups,
        "observed_window_grids_kib": sorted(observed_grids),
        "note": "Single operator-selected phase, line ordinals relative to supplied input, not clock times. Groups sampled separately; rounded MiB counters may overlap. Made counters are cumulative creation, not live or resident memory. Holder categories are Arc/COM reference proxies, not exclusive owners or unique object counts; window-use and asked-span lines iterate map entries, while the main window census deduplicates objects. Coverage is title address coverage not physical residency; sweep totals are cumulative release accounting, not immediate physical RAM returned; no sums, ownership attribution, leak diagnosis, or causal timing inference. Missing group or invalid record is not zero. Endpoint change is not allocation/release throughput. Descending cumulative values may indicate reset or log ordering. No raw log text, paths, addresses or identifiers.",
    }


# Compare only corresponding fields in independent producer groups.
# No cross-group subtraction: the primary census deduplicates windows,
# whereas coverage/holder observations may count repeated map entries.
GRID_METRICS = {
    "memory": ("working_set_mib", "private_mib", "system_free_mib",
               "host_copies", "host_copy_mib", "windows", "window_mib",
               "snapshot_reserved_mib", "texture_staging_mib", "host_texture_mib"),
    "holders": ("windows_in_slots", "windows_in_slots_mib", "windows_in_lists",
                "windows_in_lists_mib", "window_pages_ever_copied_mib",
                "windows_unknown_length", "windows_unknown_length_mib"),
    "coverage": ("window_mib", "title_window_coverage_mib", "lists_never_reset"),
    "sweep": ("window_asked_span_mib",),
}


def clean(group):
    return (group["valid_records"] > 0 and group["invalid_records"] == 0
            and group["descending_cumulative_records"] == 0)


def compare_grids(baseline, candidate, confirmed=False):
    a, b = baseline["groups"], candidate["groups"]
    issues = []
    if not confirmed:
        issues.append("matched_completed_phase_not_operator_confirmed")
    for report, groups, expected, label in (
            (baseline, a, 4096, "baseline"), (candidate, b, 2048, "candidate")):
        if report.get("observed_window_grids_kib") != [expected] or not clean(groups["holders"]):
            issues.append(label + "_grid_evidence_invalid_or_missing")
        if not clean(groups["memory"]) or not clean(groups["coverage"]):
            issues.append(label + "_primary_or_coverage_evidence_invalid_or_missing")
    observations = {}
    for group, fields in GRID_METRICS.items():
        usable = not issues and clean(a[group]) and clean(b[group])
        observations[group] = {
            "baseline_records": a[group]["valid_records"],
            "candidate_records": b[group]["valid_records"],
            "comparison_usable": bool(usable),
            "fields": {},
        }
        for field in fields:
            left = a[group]["metrics"].get(field)
            right = b[group]["metrics"].get(field)
            if left is None or right is None:
                continue
            if usable:
                observations[group]["fields"][field] = {
                    "baseline_last": left["last"], "candidate_last": right["last"],
                    "last_difference": right["last"] - left["last"],
                    "baseline_max": left["max"], "candidate_max": right["max"],
                    "max_difference": right["max"] - left["max"],
                }
    return {
        "operator_confirmed_matched_completed_phase": confirmed,
        "comparison_usable": not issues,
        "issues": issues,
        "groups": observations,
        "note": "4096 KiB control versus 2048 KiB candidate. Operator confirmation means same build, phase, settings, tails, cache and comparable restored initial headroom; both completed the bounded phase without guard stop. Not independently verified. Last and max are separate observed samples, not synchronized or equal-duration populations. Rounded capacity and holder proxies are not physical RAM savings. No cross-group arithmetic, causal inference, or gameplay acceptance. Compare local OS RSS/swap/availability trajectory and correctness separately.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="local log or operator-selected phase slice")
    parser.add_argument("--baseline-grid", type=Path, help="local 4096 KiB phase log; positional log must be 2048 KiB")
    parser.add_argument("--matched-completed-phase-confirmed", action="store_true",
                        help="operator confirms both runs completed same bounded phase without guard stop, same build/settings/tails/cache and comparable restored headroom")
    args = parser.parse_args()
    if args.matched_completed_phase_confirmed and not args.baseline_grid:
        parser.error("confirmation requires --baseline-grid")
    try:
        with args.log.open(encoding="utf-8", errors="replace") as handle:
            result = summarize(handle)
        if args.baseline_grid:
            if args.log.resolve() == args.baseline_grid.resolve():
                raise ValueError("same input")
            with args.baseline_grid.open(encoding="utf-8", errors="replace") as handle:
                baseline = summarize(handle)
            result["baseline"] = baseline
            result["grid_comparison"] = compare_grids(
                baseline, result, args.matched_completed_phase_confirmed)
    except (OSError, ValueError):
        print(json.dumps({"status": "unavailable"}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    if args.baseline_grid and not result["grid_comparison"]["comparison_usable"]:
        return 2
    return 0 if any(g["valid_records"] for g in result["groups"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
