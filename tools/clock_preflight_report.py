#!/usr/bin/env python3
"""Offline D21 status/guard JSONL summary. Does not operate a live guard."""
import argparse
import json
import statistics

FIELDS = {
    "status": frozenset(("RssAnon", "RssFile", "RssShmem", "VmSwap")),
    "guard": frozenset(("MemAvailable", "SwapFree")),
}
OUTCOMES = {0: "valid", 1: "unavailable", 2: "invalid", 3: "identity_change"}
MAX_ROWS = 100000
MAX_LINE = 16384
BASE = frozenset(("sequence", "scheduled_relative_ns", "read_start_relative_ns",
                  "read_end_relative_ns", "outcome_code", "available_fields",
                  "values_bytes"))
STOP = frozenset(("stop_before_relative_ns", "stop_after_relative_ns"))


def uint(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def read_rows(path):
    with open(path, "rb") as source:
        for index in range(MAX_ROWS + 1):
            line = source.readline(MAX_LINE + 1)
            if not line:
                return
            if index == MAX_ROWS or len(line) > MAX_LINE:
                raise ValueError("input limit exceeded")
            yield json.loads(line, object_pairs_hook=unique_object)


def summary(values):
    if not values:
        return {"count": 0, "median_ns": None, "max_ns": None}
    return {"count": len(values), "median_ns": statistics.median(values),
            "max_ns": max(values)}


def summarize_stream(rows, kind, expected, period_ns):
    if kind not in FIELDS or not uint(expected) or expected == 0 or expected > MAX_ROWS:
        raise ValueError("invalid stream or expected count")
    if not uint(period_ns) or period_ns == 0:
        raise ValueError("invalid cadence")
    outcomes = dict.fromkeys(OUTCOMES.values(), 0)
    field_counts = dict.fromkeys(sorted(FIELDS[kind]), 0)
    valid_cost, lateness, accepted = [], [], []
    invalid_rows, skipped, cadence_errors = 0, 0, 0
    prior_seq, prior_schedule, prior_end, stop = -1, None, None, None
    for row in rows:
        if not isinstance(row, dict) or not BASE <= row.keys():
            invalid_rows += 1
            continue
        extras = row.keys() - BASE
        if extras and (kind != "guard" or extras != STOP):
            invalid_rows += 1
            continue
        seq, schedule, start, end, outcome = (
            row[key] for key in ("sequence", "scheduled_relative_ns",
                                 "read_start_relative_ns", "read_end_relative_ns",
                                 "outcome_code"))
        if (not all(map(uint, (seq, schedule, start, end, outcome)))
                or seq >= expected or seq <= prior_seq or outcome not in OUTCOMES
                or start < schedule or end < start
                or (prior_end is not None and start < prior_end)
                or stop is not None):
            invalid_rows += 1
            continue
        fields, values = row["available_fields"], row["values_bytes"]
        if (not isinstance(fields, list) or not all(isinstance(x, str) for x in fields)
                or len(fields) != len(set(fields)) or not set(fields) <= FIELDS[kind]
                or not isinstance(values, dict) or set(values) != set(fields)
                or not all(map(uint, values.values()))):
            invalid_rows += 1
            continue
        if extras:
            before, after = (row[key] for key in ("stop_before_relative_ns",
                                                  "stop_after_relative_ns"))
            if not uint(before) or not uint(after) or before < end or after < before:
                invalid_rows += 1
                continue
            stop = (before, after)
        gap = seq - prior_seq
        skipped += gap - 1
        if prior_schedule is not None and schedule - prior_schedule != gap * period_ns:
            cadence_errors += 1
        prior_seq, prior_schedule, prior_end = seq, schedule, end
        outcomes[OUTCOMES[outcome]] += 1
        lateness.append(start - schedule)
        if outcome == 0:
            valid_cost.append(end - start)
            for field in fields:
                field_counts[field] += 1
        accepted.append((start, end, outcome))
    skipped += expected - prior_seq - 1
    return {
        "expected": expected, "accepted_rows": len(accepted),
        "malformed_or_out_of_order_rows": invalid_rows,
        "unobserved_sequence_slots": skipped, "cadence_errors": cadence_errors,
        "outcomes": outcomes, "valid_field_coverage": field_counts,
        "valid_read_cost": summary(valid_cost),
        "accepted_start_lateness": summary(lateness),
        "stop_dispatch_ns": None if stop is None else stop[1] - stop[0],
        "stop_observed": stop is not None,
    }, accepted, stop


def report(status_rows, guard_rows, expected, period_ns, shared_origin=False):
    status, status_intervals, _ = summarize_stream(status_rows, "status", expected, period_ns)
    guard, _, stop = summarize_stream(guard_rows, "guard", expected, period_ns)
    # The producer has no capture ID; independent input files cannot prove
    # a shared clock origin. A read spanning the stop bracket is evidence
    # of temporal overlap, not proof of process termination or causation.
    clean = all(not stream["malformed_or_out_of_order_rows"] and not stream["cadence_errors"]
                for stream in (status, guard))
    spanning = None
    if shared_origin and stop is not None and clean:
        spanning = sum(start < stop[0] and end > stop[1]
                       for start, end, _ in status_intervals)
    return {
        "status": status, "guard": guard,
        "shared_origin_operator_attested": shared_origin is True,
        "status_read_spans_stop_dispatch_count": spanning,
        "synthetic_preflight_only": True,
        "title_workload_overhead_verified": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("status")
    p.add_argument("guard")
    p.add_argument("--expected", type=int, required=True)
    p.add_argument("--period-ns", type=int, required=True)
    p.add_argument("--shared-origin", action="store_true",
                   help="attest both inputs belong to one synthetic capture")
    args = p.parse_args()
    try:
        result = report(read_rows(args.status), read_rows(args.guard), args.expected,
                        args.period_ns, args.shared_origin)
    except (OSError, ValueError, UnicodeError, RecursionError, OverflowError):
        print(json.dumps({"input_error": True}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
