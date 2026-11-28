#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate extracted selector-only timing rows (AI5 producer 27c8e1ed).

Input is one ordered, reviewed numeric receipt, not a raw log. This does
not authenticate the build, native test result, or timing environment.
"""
import argparse
import json
import re
from pathlib import Path
from statistics import median

PRODUCER = "27c8e1ed06bcbe48d241bc4b5a9f8d96350c43d4"
LANES = (1, 8, 32, 64, 256)
OCCUPANCY = ("empty", "sparse", "dense")
REPEATS = 5
ATTEMPTS = 2000
WARMUP = 256
# Rust Duration::as_nanos is u128; cap to that producer type.
MAX_NS = 2**128 - 1
PATTERN = re.compile(
    r"storage_selector_timing lanes=([0-9]{1,3}) occupancy=(empty|sparse|dense)"
    r" nonempty=([0-9]{1,3}) repeat=([0-9]) mode=([01])"
    r" warmup=([0-9]{1,4}) attempts=([0-9]{1,4})"
    r" selected=([0-9]{1,4}) empty=([0-9]{1,4}) elapsed_ns=([0-9]{1,39})"
)


def expected_keys():
    return [(n, occupancy, repeat, mode)
            for n in LANES for occupancy in OCCUPANCY
            for repeat in range(REPEATS)
            for mode in (repeat % 2, 1 - repeat % 2)]


def nonempty_count(n, occupancy):
    return {"empty": 0, "sparse": (n + 7) // 8,
            "dense": n - n // 4}[occupancy]


def summarize(lines):
    keys = expected_keys()
    expected = set(keys)
    rows = {}
    order = []
    errors = dict.fromkeys(("malformed", "unexpected", "duplicate",
                            "invalid_counts", "zero_or_overflow_time"), 0)
    seen = 0
    for line in lines:
        if not line.strip():
            continue
        seen += 1
        m = PATTERN.fullmatch(line.rstrip("\r\n"))
        if m is None:
            errors["malformed"] += 1
            continue
        n = int(m[1])
        occupancy = m[2]
        nonempty, repeat, mode, warmup, attempts, selected, empty, elapsed = (
            int(x) for x in m.groups()[2:])
        key = (n, occupancy, repeat, mode)
        if key not in expected:
            errors["unexpected"] += 1
            continue
        if key in order:
            errors["duplicate"] += 1
            continue
        order.append(key)
        if (nonempty != nonempty_count(n, occupancy) or warmup != WARMUP
                or attempts != ATTEMPTS
                or selected != (ATTEMPTS if nonempty else 0)
                or empty != attempts - selected):
            errors["invalid_counts"] += 1
            continue
        if not 0 < elapsed <= MAX_NS:
            errors["zero_or_overflow_time"] += 1
            continue
        rows[key] = elapsed
    missing = len(expected - rows.keys())
    order_valid = order == keys
    valid = not any(errors.values()) and not missing and order_valid
    result = {"producer_schema": PRODUCER, "scope": "selector_only",
              "provenance_verified": False, "valid": valid,
              "expected_rows": len(keys), "seen_rows": seen,
              "valid_rows": len(rows), "missing_or_invalid_rows": missing,
              "order_valid": order_valid, "errors": errors, "cases": []}
    if not valid:
        return result
    for n in LANES:
        for occupancy in OCCUPANCY:
            pairs = []
            for repeat in range(REPEATS):
                off = rows[n, occupancy, repeat, 0] / ATTEMPTS
                on = rows[n, occupancy, repeat, 1] / ATTEMPTS
                pairs.append({"repeat": repeat, "first_mode": repeat % 2,
                              "off_ns_per_attempt": off, "on_ns_per_attempt": on,
                              "on_minus_off_ns_per_attempt": on - off,
                              "on_over_off": on / off})
            def stats(values):
                return {"median": median(values), "min": min(values),
                        "max": max(values)}
            result["cases"].append({
                "lanes": n, "occupancy": occupancy,
                "nonempty": nonempty_count(n, occupancy), "pairs": pairs,
                "off_ns_per_attempt": stats([p["off_ns_per_attempt"] for p in pairs]),
                "on_ns_per_attempt": stats([p["on_ns_per_attempt"] for p in pairs]),
                "paired_difference_ns_per_attempt": stats(
                    [p["on_minus_off_ns_per_attempt"] for p in pairs]),
                "paired_on_over_off": stats([p["on_over_off"] for p in pairs]),
                "by_first_mode": [
                    {"mode": mode, "pair_count": sum(p["first_mode"] == mode for p in pairs),
                     "difference_ns_per_attempt": stats(
                         [p["on_minus_off_ns_per_attempt"] for p in pairs
                          if p["first_mode"] == mode])}
                    for mode in (0, 1)],
            })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        with args.receipt.open(encoding="utf-8") as receipt:
            report = summarize(receipt)
    except (OSError, UnicodeError):
        parser.exit(2, "Unable to read numeric selector receipt\n")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
