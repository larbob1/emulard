# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only model of explicit dstorage Vec requests, not actual heap/RSS.

Pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4.
Models execute/read_source/into_destination/staging_bytes only. Does not
model allocator rounding, decoder internals, page views or borrowed memory.
The early-source-drop option is a proposal, not an applied runtime change.
"""
from dataclasses import dataclass
import unittest

MIB = 1 << 20


@dataclass(frozen=True)
class Request:
    source: int
    destination: int
    intermediate: int = 0
    memory: bool = False
    pages: bool = False
    zlib: bool = False
    bcpack: bool = False

    def staging(self):
        return self.source if not self.memory and (self.pages or self.zlib or self.bcpack) else 0


def trace(r, *, fallback=False, outcome="ok", retries=0, produced=None, early_drop=False):
    """Return (event, requested-live-by-kind) snapshots for one synthetic job.

    outcome selects a reached error point. No claim about actual xmem partial
    writes: publication markers model calls, not successful host mutations.
    'truncate' leaves the intermediate allocation's requested size live.
    """
    if fallback and not r.pages:
        raise ValueError("fallback requires physical destination")
    if outcome not in {"ok", "read_error", "inflate_error", "fill_error", "write_error"}:
        raise ValueError("unknown outcome")
    if retries < 0 or (retries and not fallback):
        raise ValueError("invalid retries")
    compressed = r.zlib or r.bcpack
    chained = r.zlib and r.bcpack
    if min(r.source, r.destination, r.intermediate) < 0 or (not compressed and r.source > r.destination):
        raise ValueError("invalid request lengths")
    if outcome == "inflate_error" and not chained:
        raise ValueError("not a chained request")
    if outcome == "write_error" and not fallback:
        raise ValueError("no physical fallback write")
    if outcome == "read_error" and r.memory:
        raise ValueError("no file read")
    length = r.destination if compressed else r.source
    n = length if produced is None else produced
    if not 0 <= n <= length:
        raise ValueError("invalid produced length")
    live = {}
    events = []

    def mark(name):
        events.append((name, live.copy()))

    def alloc(kind, size):
        assert kind not in live
        live[kind] = size
        mark("alloc_" + kind)

    def drop(kind):
        live.pop(kind)
        mark("drop_" + kind)

    def finish(ok):
        # All locals leave scope before worker publishes completion. Order of
        # these modeled drops is immaterial to aggregate requested-byte peak.
        for kind in list(live):
            drop(kind)
        mark("finish_ok" if ok else "finish_error")
        return events

    if compressed and not r.memory:
        alloc("source", r.source)
        if outcome == "read_error":
            return finish(False)
    if chained:
        alloc("intermediate", r.intermediate)
        if outcome == "inflate_error":
            return finish(False)
        mark("truncate_intermediate")
        # Rust shadowing alone does not drop the original owned Cow here.
        if early_drop and "source" in live:
            drop("source")
    if fallback:
        alloc("fallback", length)
    else:
        mark("direct_begin")
    if not compressed and not r.memory and not r.pages:
        alloc("bounce", r.source)
        if outcome == "read_error":
            drop("bounce")
            mark("notify_direct")
            return finish(False)
        drop("bounce")
    if outcome in {"read_error", "fill_error"}:
        if not fallback:
            mark("notify_direct")
        return finish(False)
    mark("fill_ok")
    if fallback:
        for _ in range(retries):
            mark("retry_wait")
        if outcome == "write_error":
            mark("write_refused")
            return finish(False)
        mark("publish_prefix_" + str(n))
        drop("fallback")
    else:
        mark("notify_direct")
    return finish(True)


def peak(events):
    return max(sum(live.values()) for _, live in events)


class StorageBufferLifetimeTests(unittest.TestCase):
    def test_raw_file_bounce_not_in_staging(self):
        r = Request(8 * MIB, 16 * MIB)
        self.assertEqual(r.staging(), 0)
        self.assertEqual(peak(trace(r)), 8 * MIB)
        e = trace(r, outcome="read_error")
        self.assertEqual(e[-1], ("finish_error", {}))
        self.assertIn(("notify_direct", {}), e)

    def test_raw_page_direct_vs_fallback_uses_source_length(self):
        r = Request(8 * MIB, 16 * MIB, pages=True)
        self.assertEqual(r.staging(), 8 * MIB)
        self.assertEqual(peak(trace(r)), 0)
        self.assertEqual(peak(trace(r, fallback=True)), 8 * MIB)

    def test_borrowed_source_zero_staging_but_fallback_allocates(self):
        r = Request(8 * MIB, 32 * MIB, memory=True, pages=True, zlib=True)
        self.assertEqual(r.staging(), 0)
        self.assertEqual(peak(trace(r)), 0)
        self.assertEqual(peak(trace(r, fallback=True)), 32 * MIB)

    def test_chained_source_drop_candidate(self):
        r = Request(8 * MIB, 32 * MIB, 16 * MIB, pages=True, zlib=True, bcpack=True)
        a = trace(r, fallback=True, retries=2)
        b = trace(r, fallback=True, retries=2, early_drop=True)
        self.assertEqual(r.staging(), 8 * MIB)
        self.assertEqual(peak(a), 56 * MIB)
        self.assertEqual(peak(b), 48 * MIB)
        for events, expected in ((a, 56), (b, 48)):
            waits = [sum(live.values()) for event, live in events if event == "retry_wait"]
            self.assertEqual(waits, [expected * MIB] * 2)
            self.assertEqual(events[-1], ("finish_ok", {}))
        self.assertEqual(peak(trace(r)), 24 * MIB)
        self.assertEqual(peak(trace(r, early_drop=True)), 24 * MIB)

    def test_early_drop_does_not_change_borrowed_or_single_stage(self):
        for r in (Request(8, 32, 16, True, True, True, True),
                  Request(8, 32, pages=True, zlib=True),
                  Request(8, 32, pages=True, bcpack=True)):
            self.assertEqual(trace(r, fallback=True), trace(r, fallback=True, early_drop=True))

    def test_failures_release_and_preserve_publication_distinction(self):
        r = Request(8, 32, 16, pages=True, zlib=True, bcpack=True)
        for early in (False, True):
            for failure in ("read_error", "inflate_error", "fill_error", "write_error"):
                e = trace(r, fallback=True, outcome=failure, early_drop=early)
                self.assertEqual(e[-1], ("finish_error", {}))
                self.assertFalse(any(k.startswith("publish_prefix_") for k, _ in e))
            e = trace(r, outcome="fill_error", early_drop=early)
            self.assertIn("notify_direct", [k for k, _ in e])
            self.assertEqual(e[-1], ("finish_error", {}))

    def test_short_fill_retains_requested_extent_until_write(self):
        r = Request(8, 32, pages=True, zlib=True)
        e = trace(r, fallback=True, retries=1, produced=5)
        self.assertIn(("retry_wait", {"source": 8, "fallback": 32}), e)
        self.assertIn(("publish_prefix_5", {"source": 8, "fallback": 32}), e)
        self.assertEqual(e[-1], ("finish_ok", {}))

    def test_four_admitted_jobs_can_overlap_above_staging(self):
        r = Request(8 * MIB, 32 * MIB, 16 * MIB, pages=True, zlib=True, bcpack=True)
        staged = 0
        for _ in range(4):
            self.assertTrue(staged == 0 or staged + r.staging() <= 32 * MIB)
            staged += r.staging()
        self.assertEqual(staged, 32 * MIB)
        # Possible simultaneous retry phase, not a measured workload.
        self.assertEqual(4 * peak(trace(r, fallback=True)), 224 * MIB)
        self.assertEqual(4 * peak(trace(r, fallback=True, early_drop=True)), 192 * MIB)


if __name__ == "__main__":
    unittest.main()
