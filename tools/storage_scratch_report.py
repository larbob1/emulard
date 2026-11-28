#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate one extracted, ordered seven-cap scratch allocation receipt.

Specific to the standalone unoptimized AI5 fixture, not runtime telemetry.
Input contains only bare mixed-call rows; source/build provenance is external.
"""
import argparse
import json
from pathlib import Path
import re

PRODUCER = "101b8415d9437dc70417707fdedffa572b0f8fd3"
PREFIX = "Storage scratch mixed calls: "
MODES = (("disabled", 0), ("bounded", 65536), ("cap4k", 4096),
         ("cap8k", 8192), ("cap16k", 16384), ("cap32k", 32768),
         ("cap128k", 131072))
COUNTERS = ("cap", "requests", "failed", "nonzero", "input_bytes",
            "baseline_acquisitions", "baseline_requested", "reuse_acquisitions",
            "reuse_realloc", "reuse_requested", "reuse_dealloc", "hits",
            "trim_events", "peak_idle", "final_idle")
FIXED = {"requests": 128, "failed": 16, "nonzero": 120,
         "input_bytes": 2458368, "baseline_acquisitions": 120,
         "baseline_requested": 2458368, "trim_events": 9, "final_idle": 0}
MAX_U64 = 2**64 - 1


def parse(line):
    if not line.startswith(PREFIX):
        return None
    fields = {}
    for token in line[len(PREFIX):].split():
        key, sep, value = token.partition("=")
        if not sep or key in fields or not value:
            return None
        if key == "mode":
            if value not in dict(MODES):
                return None
            fields[key] = value
        elif key in COUNTERS:
            if not re.fullmatch(r"[0-9]{1,20}", value):
                return None
            n = int(value)
            if n > MAX_U64:
                return None
            fields[key] = n
        else:
            return None
    return fields if set(fields) == {"mode", *COUNTERS} else None


def consistent(row):
    if row["cap"] != dict(MODES)[row["mode"]]:
        return False
    if any(row[k] != v for k, v in FIXED.items()):
        return False
    acquisitions, realloc, dealloc, hits = (
        row[k] for k in ("reuse_acquisitions", "reuse_realloc", "reuse_dealloc", "hits"))
    # Exact fixture: each nonzero request either hits or makes one acquisition.
    # Reallocations are included in acquisitions, but not new live allocations.
    if (acquisitions + hits != row["nonzero"] or realloc > acquisitions
            or acquisitions - realloc != dealloc
            or row["peak_idle"] > row["cap"]
            or (acquisitions > 0 and row["reuse_requested"] == 0)):
        return False
    if row["cap"] == 0:
        return (hits == realloc == row["peak_idle"] == 0
                and acquisitions == dealloc == row["baseline_acquisitions"]
                and row["reuse_requested"] == row["baseline_requested"])
    # Preserve the producer's existing 64 KiB improvement assertion only.
    if row["mode"] == "bounded":
        return hits > 0 and acquisitions < row["baseline_acquisitions"]
    return True


def summarize(lines):
    rows = {}
    seen_order = []
    errors = dict.fromkeys(("malformed", "duplicate", "inconsistent"), 0)
    seen = 0
    for line in lines:
        if not line.strip():
            continue
        seen += 1
        row = parse(line.rstrip("\r\n"))
        if row is None:
            errors["malformed"] += 1
            continue
        mode = row["mode"]
        if mode in seen_order:
            errors["duplicate"] += 1
            continue
        seen_order.append(mode)
        if not consistent(row):
            errors["inconsistent"] += 1
            continue
        rows[mode] = row
    order_valid = seen_order == [mode for mode, _ in MODES]
    valid = order_valid and not any(errors.values()) and len(rows) == len(MODES)
    result = {
        "producer_schema": PRODUCER,
        "scope": "standalone_unoptimized_allocator_interface",
        "provenance_verified": False,
        "valid": valid, "order_valid": order_valid, "seen_rows": seen,
        "valid_rows": len(rows), "expected_rows": len(MODES),
        "errors": errors, "cases": [],
        "limitations": ["not runtime timing or RSS",
                        "requested sizes include full realloc size",
                        "peak idle sampled after operation, not peak transient memory",
                        "explicit fixture trims, not observed OS pressure"],
    }
    if not valid:
        return result
    for mode, _ in MODES:
        row = rows[mode]
        result["cases"].append({
            **row,
            "acquisition_calls_saved": row["baseline_acquisitions"] - row["reuse_acquisitions"],
            "requested_size_difference_bytes": row["reuse_requested"] - row["baseline_requested"],
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        with args.receipt.open(encoding="utf-8") as receipt:
            result = summarize(receipt)
    except (OSError, UnicodeError):
        parser.exit(2, "Unable to read numeric scratch receipt\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
