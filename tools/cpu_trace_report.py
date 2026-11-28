#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Summarize CPU-only present-call-return windows, not a causal GPU trace."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import median

KINDS = ("execute", "pace_sleep", "present_call")
MAX_U64 = 2**64 - 1
MAX_SPANS = 256
MAX_WINDOWS = 600


def uint(x):
    return type(x) is int and 0 <= x <= MAX_U64


def analyze(record):
    if not isinstance(record, dict) or record.get("schema") != "cpu_trace_v1":
        raise ValueError("schema")
    if record.get("boundary") != "present_call_return":
        raise ValueError("boundary")
    for key in ("sequence", "start_ns", "end_ns", "dropped", "invalid"):
        if not uint(record.get(key)):
            raise ValueError("numeric_field")
    for key in ("thread_changed", "present_ok", "cpu_window_complete"):
        if type(record.get(key)) is not bool:
            raise ValueError("boolean_field")
    if record["sequence"] == 0 or record["start_ns"] >= record["end_ns"]:
        raise ValueError("invalid_window")
    spans = record.get("spans")
    if not isinstance(spans, list) or len(spans) > MAX_SPANS:
        raise ValueError("span_limit")
    if (record["dropped"] or record["invalid"] or record["thread_changed"]
            or not record["present_ok"] or not record["cpu_window_complete"]):
        return None
    totals = dict.fromkeys(KINDS, 0)
    count = dict.fromkeys(KINDS, 0)
    previous = record["start_ns"]
    for span in spans:
        if not isinstance(span, dict):
            raise ValueError("span")
        kind, a, b = span.get("kind"), span.get("start_ns"), span.get("end_ns")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError("span_kind")
        if not uint(a) or not uint(b) or not previous <= a < b <= record["end_ns"]:
            raise ValueError("span_overlap_or_bounds")
        if kind == "present_call" and b != record["end_ns"]:
            raise ValueError("present_boundary")
        previous = b
        totals[kind] += b - a
        count[kind] += 1
    if count["present_call"] != 1:
        raise ValueError("missing_or_repeated_present")
    wall = record["end_ns"] - record["start_ns"]
    return {"wall_ns": wall, "elapsed_by_kind_ns": totals, "calls_by_kind": count,
            "unattributed_ns": wall - sum(totals.values())}


REASONS = frozenset(("schema", "boundary", "numeric_field", "boolean_field",
                     "invalid_window", "span_limit", "span", "span_kind",
                     "span_overlap_or_bounds", "present_boundary",
                     "missing_or_repeated_present"))


def tails(values):
    values = sorted(values)
    return {"median_ms": median(values) / 1e6,
            "p95_ms": values[math.ceil(.95 * len(values)) - 1] / 1e6,
            "p99_ms": values[math.ceil(.99 * len(values)) - 1] / 1e6,
            "max_ms": values[-1] / 1e6}


def summarize(lines, require_terminal=False):
    reasons = Counter()
    sequence_issues = Counter()
    valid = []
    previous_sequence, previous_end = 0, None
    records = 0
    receipt = None
    for line in lines:
        if not line.strip():
            continue
        if receipt is not None:
            reasons["after_terminal"] += 1
            break
        try:
            record = json.loads(line)
            if isinstance(record, dict) and record.get("schema") == "cpu_trace_end_v1":
                receipt = record
                continue
            records += 1
            if records > MAX_WINDOWS:
                reasons["capture_limit"] += 1
                break
            row = analyze(record)
            seq, start, end = record["sequence"], record["start_ns"], record["end_ns"]
            if seq != previous_sequence + 1:
                sequence_issues["nonconsecutive_sequence"] += 1
            if previous_end is not None and start != previous_end:
                sequence_issues["discontinuous_windows"] += 1
            previous_sequence, previous_end = seq, end
            if row is None:
                reasons["incomplete_window"] += 1
            else:
                valid.append(row)
        except (ValueError, TypeError, RecursionError) as exc:
            reason = str(exc)
            reasons[reason if reason in REASONS else "malformed_record"] += 1

    terminal_ok = False
    if receipt is not None:
        counts = ("code", "expected", "attempted", "drained", "written",
                  "invalid_windows", "dropped_windows")
        terminal_ok = (all(uint(receipt.get(k)) for k in counts)
                       and receipt.get("complete") is True
                       and receipt["code"] == 1
                       and 1 <= receipt["expected"] <= MAX_WINDOWS
                       and receipt["expected"] == receipt["attempted"] == receipt["drained"]
                       == receipt["written"] == records == len(valid)
                       and receipt["invalid_windows"] == receipt["dropped_windows"] == 0)
        if not terminal_ok:
            reasons["invalid_terminal"] += 1
    elif require_terminal:
        reasons["missing_terminal"] += 1
    usable = bool(valid) and not reasons and not sequence_issues
    aggregate = None
    if usable:
        total = sum(r["wall_ns"] for r in valid)
        kind_totals = {kind: sum(r["elapsed_by_kind_ns"][kind] for r in valid)
                       for kind in KINDS}
        unattributed = sum(r["unattributed_ns"] for r in valid)
        aggregate = {
            "observed_wall_seconds": total / 1e9,
            "present_call_return_window_tails": tails([r["wall_ns"] for r in valid]),
            "elapsed_fraction_by_kind": {k: v / total for k, v in kind_totals.items()},
            "unattributed_elapsed_fraction": unattributed / total,
            "per_window_elapsed_tails_by_kind": {
                kind: tails([r["elapsed_by_kind_ns"][kind] for r in valid]) for kind in KINDS},
            "calls_by_kind": {kind: sum(r["calls_by_kind"][kind] for r in valid) for kind in KINDS},
        }
    return {"records_examined": records, "structurally_valid_windows": len(valid),
            "rejected_records": sum(reasons.values()), "rejection_reasons": dict(sorted(reasons.items())),
            "sequence_issues": dict(sorted(sequence_issues.items())),
            "all_supplied_records_usable": usable, "terminal_verified": usable and terminal_ok,
            "aggregate": aggregate,
            "note": "Selected outer presenting-thread call elapsed time only, including nested waits/work. "
                    "Not CPU busy time, display completion, GPU time, dependency attribution or visible FPS. "
                    "Fractions are elapsed-weighted; per-window tails include zero when a kind was absent. "
                    "Unattributed time is not necessarily idle. Completeness is producer-attested; "
                    "A verified terminal checks declared counts; legacy mode cannot detect missing trailing records. "
                    "Uninstrumented calls cannot be detected. "
                    "Capture limit stops examination at first excess record. No raw timestamps or IDs exported."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--require-terminal", action="store_true",
                        help="reject captures without a matching final receipt")
    args = parser.parse_args()
    try:
        with args.trace.open(encoding="utf-8", errors="replace") as handle:
            report = summarize(handle, require_terminal=args.require_terminal)
    except OSError:
        print(json.dumps({"status": "trace_unavailable"}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["all_supplied_records_usable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
