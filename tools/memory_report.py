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
        "note": "Single operator-selected phase, line ordinals relative to supplied input, not clock times. Groups sampled separately; rounded MiB counters may overlap. Made counters are cumulative creation, not live or resident memory. Holder categories may overlap, coverage is title address coverage not physical residency; no sums, ownership attribution, leak diagnosis, or causal timing inference. Missing group or invalid record is not zero. Endpoint change is not allocation/release throughput. Descending cumulative values may indicate reset or log ordering. No raw log text, paths, addresses or identifiers.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="local log or operator-selected phase slice")
    args = parser.parse_args()
    try:
        with args.log.open(encoding="utf-8", errors="replace") as handle:
            result = summarize(handle)
    except (OSError, ValueError):
        print(json.dumps({"status": "unavailable"}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if any(g["valid_records"] for g in result["groups"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
