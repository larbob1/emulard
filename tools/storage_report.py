#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Summarize allowlisted DirectStorage numeric debug windows locally."""
import argparse
import hashlib
import json
import os
from math import isfinite
from pathlib import Path
import re
from statistics import median

WINDOW = re.compile(r"\bdstorage: last ([0-9]+(?:\.[0-9]+)?) s\b")
INT_FIELDS = ("requests", "staging_waits", "waiting", "bcpack_mb")
RATE_FIELDS = ("mb_per_s", "busy_workers", "reading_workers", "bcpack_workers")
PHYSICAL_MARKERS = {
    "retry_success_lines": "dstorage: a destination's physical pages written after a retry",
    "retry_exhausted_lines": "dstorage: retries used up (VICTORY_DSTORAGE_RETRIES)",
    "physical_write_failure_lines": "dstorage: a destination's physical pages could not be written (unknown page or a host failure); its request fails",
    "early_full_queue_lines": "dstorage: a full queue's reads into physical pages start before the title's Submit",
    "half_full_queue_lines": "dstorage: a queue half full submitted itself; reads into physical pages wait for the title's Submit",
}


def numeric_field(line, name, integer=False):
    number = r"[0-9]+" if integer else r"[0-9]+(?:\.[0-9]+)?"
    matches = re.findall(rf"(?:^|\s){name}=({number})(?=\s|$)", line)
    if len(matches) != 1:
        return None
    value = int(matches[0]) if integer else float(matches[0])
    return value if integer or isfinite(value) else None


def summarize_storage(lines, skip=0):
    if skip < 0:
        raise ValueError("warmup must be nonnegative")
    configs, started, rows = [], [], []
    seen = skipped = invalid = 0
    physical = dict.fromkeys(PHYSICAL_MARKERS, 0)
    for line in lines:
        for key, marker in PHYSICAL_MARKERS.items():
            if marker in line:
                physical[key] += 1
        if "dstorage: worker configuration" in line:
            workers = numeric_field(line, "workers", True)
            default = numeric_field(line, "default", True)
            configs.append({"configured": workers, "automatic": default}
                           if workers is not None and default is not None and 0 < workers <= default else None)
        elif "dstorage: workers" in line:
            started.append(numeric_field(line, "workers", True))
        if "dstorage: last " not in line:
            continue
        seen += 1
        if seen <= skip:
            skipped += 1
            continue
        match = WINDOW.search(line)
        seconds = float(match[1]) if match else 0
        row = {key: numeric_field(line, key, key in INT_FIELDS)
               for key in INT_FIELDS + RATE_FIELDS}
        if not isfinite(seconds) or seconds <= 0 or any(value is None for value in row.values()):
            invalid += 1
            continue
        rows.append({"seconds": seconds, **row})
    elapsed = sum(row["seconds"] for row in rows)
    configuration = configs[0] if len(configs) == 1 else None
    actual = started[0] if len(started) == 1 else None
    valid_config = (configuration is not None and actual is not None
                    and 0 < actual <= configuration["configured"])
    return {
        "worker_configuration": configuration,
        "physical_destination_observations": physical,
        "physical_destination_failure_observed": bool(
            physical["retry_exhausted_lines"] or physical["physical_write_failure_lines"]),
        "physical_destination_attempt_evidence": bool(
            physical["retry_success_lines"] or physical["retry_exhausted_lines"]
            or physical["physical_write_failure_lines"]),
        "storage_page_lookup_execution_verified": False,
        "physical_destination_note": "Matching message lines across the entire supplied log, including warmup, not unique requests. Retry messages indicate physical-destination activity; queue messages alone do not establish that a physical write ran. Ordinary successful page-window writes may be silent. No proof of lookup flag execution, path coverage, or no failure from absent messages.",
        "workers_started": actual,
        "configuration_records": len(configs),
        "worker_start_records": len(started),
        "worker_configuration_verified": valid_config,
        "windows_seen": seen,
        "windows_skipped": skipped,
        "windows_invalid_after_warmup": invalid,
        "windows_used": len(rows),
        "reported_window_seconds": round(elapsed, 3),
        "finished_requests": sum(row["requests"] for row in rows) if rows else None,
        "approx_destination_mb": round(sum(row["seconds"] * row["mb_per_s"] for row in rows), 3) if rows else None,
        "weighted_destination_mb_per_s": round(sum(row["seconds"] * row["mb_per_s"] for row in rows) / elapsed, 3) if rows else None,
        "weighted_busy_workers": round(sum(row["seconds"] * row["busy_workers"] for row in rows) / elapsed, 3) if rows else None,
        "weighted_reading_workers": round(sum(row["seconds"] * row["reading_workers"] for row in rows) / elapsed, 3) if rows else None,
        "weighted_bcpack_workers": round(sum(row["seconds"] * row["bcpack_workers"] for row in rows) / elapsed, 3) if rows else None,
        "staging_waits": sum(row["staging_waits"] for row in rows) if rows else None,
        "waiting_snapshot_median": median(row["waiting"] for row in rows) if rows else None,
        "waiting_snapshot_max": max((row["waiting"] for row in rows), default=None),
        "note": "Reported activity windows only; idle periods and trailing partial windows may be absent. Rounded destination throughput counts finished requests, not verified successful I/O. Waiting is a queue snapshot, not starvation duration; staging waits are a count. Worker time overlaps. Configuration and workload must be verified separately.",
    }


def compare_storage(baseline, candidate):
    usable = all(report["worker_configuration_verified"] and report["windows_used"]
                 and (report["finished_requests"] or 0) > 0
                 and report.get("physical_destination_failure_observed") is False
                 and not report["windows_invalid_after_warmup"] for report in (baseline, candidate))
    a, b = (report["weighted_destination_mb_per_s"] for report in (baseline, candidate))
    return {
        "comparison_usable": usable,
        "storage_page_lookup_execution_verified": False,
        "physical_destination_failure_observed": any(
            report.get("physical_destination_failure_observed") is True
            for report in (baseline, candidate)),
        "destination_rate_ratio": round(b / a, 4) if usable and a > 0 else None,
        "destination_rate_delta": round(b - a, 3) if usable else None,
        "note": "Compare matched workload, cache state, log level and warmup. Window throughput is not gameplay FPS or successful-I/O throughput.",
    }


def read_storage_log(path, skip):
    # Hash the same normalized decoded stream used by the parser; never
    # emit the fingerprint or source path. Common concurrent edits refuse.
    digest = hashlib.sha256()
    with path.open(encoding="utf-8", errors="replace", newline=None) as handle:
        before = os.fstat(handle.fileno())

        def observed():
            for line in handle:
                digest.update(line.rstrip("\n").encode("utf-8"))
                digest.update(b"\n")
                yield line

        report = summarize_storage(observed(), skip)
        after = os.fstat(handle.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("input_changed_during_read")
    return report, digest.digest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--skip", type=int, default=1, help="skip initial debug windows")
    args = parser.parse_args()
    if args.skip < 0:
        parser.error("warmup must be nonnegative")
    try:
        result, fingerprint = read_storage_log(args.log, args.skip)
        if args.baseline:
            if args.log.resolve() == args.baseline.resolve():
                raise ValueError("repeated_input_path")
            baseline, baseline_fingerprint = read_storage_log(args.baseline, args.skip)
            if fingerprint == baseline_fingerprint:
                raise ValueError("repeated_log_content")
            result["baseline"] = baseline
            result["comparison"] = compare_storage(baseline, result)
    except (OSError, ValueError) as exc:
        reason = str(exc)
        allowed = {"repeated_input_path", "repeated_log_content", "input_changed_during_read"}
        print(json.dumps({"status": "storage log unavailable",
                          "reason": reason if reason in allowed else "invalid_or_unavailable"}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["windows_used"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
