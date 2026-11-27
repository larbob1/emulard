#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Analyze explicit, frame-local timestamp/dependency traces; no inferred edges."""
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median

KINDS = frozenset(("cpu_record", "cpu_submit", "mapping", "texture", "pipeline",
                   "gpu", "fence_wait", "storage", "present", "other"))
MAX_SPANS = 100000


def integer(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def union_length(intervals):
    total = 0
    end = None
    for start, stop in sorted(intervals):
        if end is None or start >= end:
            total += stop - start
            end = stop
        elif stop > end:
            total += stop - end
            end = stop
    return total


def analyze(frame):
    """A measured dependency-chain lower bound, not a scheduler simulation."""
    if not isinstance(frame, dict) or frame.get("schema") != 1:
        raise ValueError("invalid_schema")
    if not integer(frame.get("frame")):
        raise ValueError("invalid_frame_id")
    start, end = frame.get("start_us"), frame.get("end_us")
    if not integer(start) or not integer(end) or start >= end:
        raise ValueError("invalid_frame_window")
    loss = frame.get("lost_spans")
    if not integer(loss):
        raise ValueError("invalid_loss_count")
    if frame.get("clock") != "host_monotonic_calibrated":
        return {"status": "insufficient_evidence", "reason": "unsynchronized_clock"}
    if frame.get("complete") is not True or loss:
        return {"status": "insufficient_evidence", "reason": "incomplete_or_lost_spans"}
    spans = frame.get("spans")
    terminal = frame.get("terminal")
    if not isinstance(spans, list) or not spans or len(spans) > MAX_SPANS or not integer(terminal):
        raise ValueError("invalid_spans_or_terminal")
    nodes = {}
    for span in spans:
        if not isinstance(span, dict):
            raise ValueError("invalid_span")
        sid, a, b = span.get("id"), span.get("start_us"), span.get("end_us")
        kind, predecessors = span.get("kind"), span.get("depends_on")
        if not integer(sid) or sid in nodes:
            raise ValueError("invalid_or_duplicate_span_id")
        if not integer(a) or not integer(b) or not start <= a < b <= end:
            raise ValueError("span_outside_window_or_nonpositive")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError("unknown_span_kind")
        if not isinstance(predecessors, list) or any(not integer(p) for p in predecessors):
            raise ValueError("invalid_dependencies")
        if len(set(predecessors)) != len(predecessors) or sid in predecessors:
            raise ValueError("duplicate_or_self_dependency")
        nodes[sid] = (a, b, kind, predecessors)
    if terminal not in nodes or nodes[terminal][2] != "present" or nodes[terminal][1] != end:
        raise ValueError("invalid_presentation_terminal")
    for a, b, kind, predecessors in nodes.values():
        for pred in predecessors:
            if pred not in nodes:
                raise ValueError("missing_dependency")
            if nodes[pred][1] > a:
                # Inclusive wait spans and cross-clock timestamps must not
                # be added as serial dependencies.
                raise ValueError("overlapping_or_reversed_dependency")

    # Positive intervals plus end-before-start edges imply a DAG. Sort
    # by start time, which is strictly increasing along every edge.
    longest, choices, ties = {}, {}, {}
    for sid in sorted(nodes, key=lambda key: nodes[key][0]):
        a, b, kind, predecessors = nodes[sid]
        best = max((longest[p] for p in predecessors), default=0)
        winners = [p for p in predecessors if longest[p] == best]
        longest[sid] = best + b - a
        choices[sid] = winners[0] if winners else None
        ties[sid] = len(winners) > 1 or any(ties[p] for p in winners)

    ancestors = set()
    pending = [terminal]
    while pending:
        sid = pending.pop()
        if sid in ancestors:
            continue
        ancestors.add(sid)
        pending.extend(nodes[sid][3])

    required_union = union_length((nodes[s][0], nodes[s][1]) for s in ancestors)
    all_union = union_length((a, b) for a, b, _, _ in nodes.values())
    required_total = sum(nodes[s][1] - nodes[s][0] for s in ancestors)
    chain = longest[terminal]
    breakdown = None
    if not ties[terminal]:
        counts = Counter()
        at = terminal
        while at is not None:
            a, b, kind, _ = nodes[at]
            counts[kind] += b - a
            at = choices[at]
        breakdown = dict(sorted(counts.items()))
    return {
        "status": "measured_dependency_chain",
        "frame_wall_us": end - start,
        "span_count": len(nodes),
        "terminal_ancestor_count": len(ancestors),
        "unrelated_span_count": len(nodes) - len(ancestors),
        "all_span_union_us": all_union,
        "terminal_ancestor_union_us": required_union,
        "terminal_ancestor_aggregate_us": required_total,
        "terminal_ancestor_overlap_excess_us": required_total - required_union,
        "longest_measured_dependency_chain_us": chain,
        "chain_category_us": breakdown,
        "equal_length_chain_ambiguity": ties[terminal],
        "wall_us_outside_selected_chain_work": end - start - chain,
        "wall_us_outside_terminal_ancestor_union": end - start - required_union,
    }


def summarize(lines):
    results = []
    rejected = Counter()
    frame_ids = set()
    duplicate = False
    records = 0
    for line in lines:
        if not line.strip():
            continue
        records += 1
        try:
            frame = json.loads(line)
            if isinstance(frame, dict) and integer(frame.get("frame")):
                fid = frame["frame"]
                if fid in frame_ids:
                    duplicate = True
                    rejected["duplicate_frame_id"] += 1
                    continue
                frame_ids.add(fid)
            result = analyze(frame)
        except (ValueError, TypeError, RecursionError) as exc:
            # Only fixed reason codes from this module are exported.
            reason = str(exc)
            allowed = ("invalid_schema", "invalid_frame_id", "invalid_frame_window",
                       "invalid_loss_count", "invalid_spans_or_terminal", "invalid_span",
                       "invalid_or_duplicate_span_id", "span_outside_window_or_nonpositive",
                       "unknown_span_kind", "invalid_dependencies", "duplicate_or_self_dependency",
                       "invalid_presentation_terminal", "missing_dependency",
                       "overlapping_or_reversed_dependency")
            rejected[reason if reason in allowed else "malformed_record"] += 1
            continue
        if result["status"] != "measured_dependency_chain":
            rejected[result["reason"]] += 1
        else:
            results.append(result)
    return {
        "records_seen": records,
        "valid_frames": len(results),
        "rejected_frames": sum(rejected.values()),
        "rejection_reasons": dict(sorted(rejected.items())),
        "all_records_usable": bool(results) and not rejected and not duplicate,
        "median_measured_chain_us": median(r["longest_measured_dependency_chain_us"] for r in results) if results and not rejected else None,
        "frames": results,
        "note": "Only explicit nonoverlapping terminal dependencies are analyzed. Chain work is a lower bound under supplied edges, not a fully attributed critical path; gaps may contain unobserved work or waits. Union measures elapsed coverage, not CPU/GPU utilization. Ambiguous equal-length chains have no category attribution. Completeness and calibration are producer assertions, not independently verified. No FPS or visible rendering evidence.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    try:
        with args.trace.open(encoding="utf-8", errors="replace") as handle:
            report = summarize(handle)
    except OSError:
        print(json.dumps({"status": "trace_unavailable"}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["all_records_usable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
