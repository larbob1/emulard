#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline tail report for existing host_profile.py JSON. Never samples a process."""
import argparse
import json
import math
from pathlib import Path

MAX_BYTES = 16 * 1024 * 1024
MAX_U64 = 2**64 - 1
FIELDS = (
    "process_status_rss_bytes", "process_anon_rss_bytes",
    "process_file_rss_bytes", "process_shmem_rss_bytes",
    "process_anon_swap_bytes", "system_available_bytes",
    "system_swap_free_bytes",
)
ROW_FIELDS = ("rss_end_bytes", "read_bytes", "snapshot_read_seconds_max")
NOTE = ("Adjacent interval-end observations only; relative time starts at "
        "the sampler's initial stat observation, not launch time. Initial "
        "memory values are absent. Status, stat and meminfo are sequential, "
        "not atomic. Shared/file RSS is not unique physical consumption; "
        "no allocation-owner, leak, phase alignment or FPS inference. "
        "Missing endpoints are not bridged; no safety-guard enforcement.")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError("non-finite JSON value")


def load_report(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("oversized report")
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def count(value):
    return type(value) is int and 0 <= value <= MAX_U64


def duration(value):
    return (type(value) in (int, float) and 0 <= value <= MAX_U64
            and math.isfinite(value))


def summarize_tail(report, tail=5):
    if type(tail) is not int or not 3 <= tail <= 5:
        raise ValueError("tail must be 3 to 5")
    if not isinstance(report, dict):
        raise ValueError("invalid report")
    intervals = report.get("intervals")
    requested = report.get("requested_intervals")
    completed = report.get("completed_intervals")
    complete = report.get("complete")
    if (not isinstance(intervals, list) or type(requested) is not int
            or type(completed) is not int or type(complete) is not bool
            or not 1 <= requested <= 3600
            or not 0 <= completed <= requested or completed != len(intervals)
            or (complete and completed != requested)):
        raise ValueError("invalid interval population")
    result = []
    elapsed = 0.0
    start = max(0, completed - tail)
    fields = FIELDS + ROW_FIELDS
    coverage = {field: {"valid": 0, "missing": 0, "invalid": 0}
                for field in fields}
    for index, row in enumerate(intervals):
        if not isinstance(row, dict):
            raise ValueError("invalid interval")
        dt = row.get("elapsed_seconds")
        if not duration(dt) or dt <= 0:
            raise ValueError("invalid interval time")
        next_elapsed = elapsed + dt
        if not math.isfinite(next_elapsed) or next_elapsed <= elapsed:
            raise ValueError("invalid cumulative time")
        elapsed = next_elapsed
        if index < start:
            continue
        memory = row.get("memory_end")
        values = {}
        invalid = []
        for field in fields:
            source = row if field in ROW_FIELDS else memory
            value = source.get(field) if isinstance(source, dict) else None
            validator = duration if field == "snapshot_read_seconds_max" else count
            malformed = (source is not None and not isinstance(source, dict))
            if malformed or (value is not None and not validator(value)):
                invalid.append(field)
                status = "invalid"
                value = None
            else:
                status = "missing" if value is None else "valid"
            coverage[field][status] += 1
            values[field] = value
        item = {"interval": index + 1, "relative_end_seconds": elapsed,
                "interval_seconds": dt, "values": values,
                "invalid_fields": invalid}
        if result:
            previous = result[-1]["values"]
            # Read bytes is an interval counter, not an endpoint quantity;
            # sample overhead is not a residency counter either.
            delta_fields = FIELDS + ("rss_end_bytes",)
            item["adjacent_endpoint_delta_bytes"] = {
                field: values[field] - previous[field]
                if values[field] is not None and previous[field] is not None
                else None for field in delta_fields}
        else:
            item["adjacent_endpoint_delta_bytes"] = None
        result.append(item)
    return {"requested_intervals": requested, "completed_intervals": completed,
            "source_complete": complete, "tail_endpoints": result,
            "tail_field_coverage": coverage, "note": NOTE}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="Existing local host_profile JSON")
    parser.add_argument("--tail", type=int, choices=range(3, 6), default=5)
    args = parser.parse_args()
    try:
        result = summarize_tail(load_report(args.report), args.tail)
    except (OSError, UnicodeError, ValueError, OverflowError, RecursionError):
        print(json.dumps({"status": "unavailable_or_invalid_report"}))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["tail_endpoints"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
