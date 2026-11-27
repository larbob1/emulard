# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure clock-bracket checks for diagnostic review; no live reads or wire parser."""

MAX_NS = 2**64 - 1


def ns(value):
    if type(value) is not int or not 0 <= value <= MAX_NS:
        raise ValueError("invalid nanoseconds")
    return value


def bracket(start, end):
    start, end = ns(start), ns(end)
    if end < start:
        raise ValueError("reversed bracket")
    return start, end


def relation(first, second):
    """For a common monotonic domain only; touching/overlap is ambiguous."""
    a, b = bracket(*first), bracket(*second)
    if a[1] < b[0]:
        return "before"
    if b[1] < a[0]:
        return "after"
    return "overlap_or_touch"


def anchor_bounds(before, realtime, after):
    """Possible realtime-minus-monotonic offset during a bracketed read."""
    before, after = bracket(before, after)
    realtime = ns(realtime)
    return realtime - after, realtime - before


def review_anchors(first, last, *, max_bracket_ns, max_offset_change_ns):
    """Compare endpoint anchors without exporting clocks or inferring stability.

    Inputs are (monotonic_before, realtime, monotonic_after), same host and
    clock domain, from one local session. Thresholds are explicit review
    parameters, not permission to run a workload. A bounded endpoint change
    does not exclude a clock step and reversal between the two observations.
    """
    max_bracket_ns = ns(max_bracket_ns)
    max_offset_change_ns = ns(max_offset_change_ns)
    a = anchor_bounds(*first)
    b = anchor_bounds(*last)
    if relation((first[0], first[2]), (last[0], last[2])) != "before":
        raise ValueError("anchor order ambiguous")
    widths = [a[1] - a[0], b[1] - b[0]]
    # Difference interval accounts for uncertainty at both anchors.
    lo, hi = b[0] - a[1], b[1] - a[0]
    minimum = 0 if lo <= 0 <= hi else min(abs(lo), abs(hi))
    maximum = max(abs(lo), abs(hi))
    if max(widths) > max_bracket_ns:
        status = "bracket_too_wide"
    elif minimum > max_offset_change_ns:
        status = "endpoint_change_exceeds_limit"
    elif maximum > max_offset_change_ns:
        status = "endpoint_change_uncertain"
    else:
        status = "endpoint_change_within_limit"
    return {
        "anchor_bracket_widths_ns": widths,
        "endpoint_offset_change_bounds_ns": [lo, hi],
        "status": status,
        "intervening_clock_stability_verified": False,
        "note": ("Endpoint consistency only; no absolute clock values, "
                 "cross-stream causation, or wall-to-monotonic conversion "
                 "is established by this check."),
    }
