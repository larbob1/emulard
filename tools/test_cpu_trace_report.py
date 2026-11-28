# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cpu_trace_report import analyze, summarize


def window(seq=1, start=100_000_000, end=200_000_000):
    return {"schema": "cpu_trace_v1", "boundary": "present_call_return",
            "sequence": seq, "start_ns": start, "end_ns": end,
            "dropped": 0, "invalid": 0, "thread_changed": False,
            "present_ok": True, "cpu_window_complete": True, "spans": [
                {"kind": "execute", "start_ns": start, "end_ns": start + 10_000_000},
                {"kind": "pace_sleep", "start_ns": start + 20_000_000, "end_ns": start + 30_000_000},
                {"kind": "present_call", "start_ns": end - 20_000_000, "end_ns": end},
            ]}


def report(*records):
    return summarize([json.dumps(r) for r in records])


class CpuTraceReportTests(unittest.TestCase):
    def test_elapsed_coverage_and_tails(self):
        a = window()
        b = window(2, 200_000_000, 400_000_000)
        b["spans"].pop(1)
        result = report(a, b)
        self.assertTrue(result["all_supplied_records_usable"])
        agg = result["aggregate"]
        self.assertAlmostEqual(agg["elapsed_fraction_by_kind"]["execute"], 20 / 300)
        self.assertAlmostEqual(agg["unattributed_elapsed_fraction"], 230 / 300)
        self.assertEqual(agg["present_call_return_window_tails"]["p95_ms"], 200)
        self.assertEqual(agg["per_window_elapsed_tails_by_kind"]["pace_sleep"]["median_ms"], 5)
        self.assertEqual(agg["calls_by_kind"]["pace_sleep"], 1)

    def test_reject_loss_and_failed_present(self):
        for key, val in (("dropped", 1), ("invalid", 1), ("thread_changed", True),
                         ("present_ok", False), ("cpu_window_complete", False)):
            f = window()
            f[key] = val
            result = report(f)
            self.assertIsNone(result["aggregate"])
            self.assertEqual(result["rejection_reasons"], {"incomplete_window": 1})

    def test_reject_span_bounds_and_overlap(self):
        for modify in (lambda f: f["spans"][1].update(start_ns=105_000_000),
                       lambda f: f["spans"][2].update(end_ns=201_000_000),
                       lambda f: f["spans"][2].update(end_ns=199_000_000),
                       lambda f: f["spans"].pop(),
                       lambda f: f["spans"][0].update(kind="gpu"),
                       lambda f: f["spans"][0].update(start_ns=True)):
            f = window()
            modify(f)
            with self.assertRaises(ValueError):
                analyze(f)

    def test_schema_not_causal_trace_and_type_checks(self):
        for key, val in (("schema", 1), ("boundary", "display_completion"),
                         ("sequence", True), ("sequence", 0), ("dropped", -1),
                         ("start_ns", 2**64), ("present_ok", 1)):
            f = window()
            f[key] = val
            self.assertIsNone(report(f)["aggregate"])

    def test_sequence_gaps_and_duplicate_windows(self):
        a = window()
        for b in (window(3, 200_000_000, 300_000_000),
                  window(2, 201_000_000, 301_000_000), a):
            r = report(a, b)
            self.assertTrue(r["sequence_issues"])
            self.assertIsNone(r["aggregate"])
        self.assertIsNone(report(window(2))["aggregate"])

    def test_capture_limit_and_empty(self):
        self.assertIsNone(summarize([])["aggregate"])
        f = window()
        f["spans"] *= 86
        self.assertEqual(report(f)["rejection_reasons"], {"span_limit": 1})
        r = summarize(json.dumps(window(i + 1, i * 100_000_000, (i+1)*100_000_000))
                      for i in range(602))
        self.assertEqual(r["records_examined"], 601)
        self.assertEqual(r["rejection_reasons"], {"capture_limit": 1})
        self.assertIsNone(r["aggregate"])

    def test_terminal_receipt_and_truncation(self):
        a = window()
        end = {"schema": "cpu_trace_end_v1", "code": 1, "expected": 1,
               "attempted": 1, "drained": 1, "written": 1,
               "invalid_windows": 0, "dropped_windows": 0, "complete": True}
        def strict(*rows):
            return summarize([json.dumps(r) for r in rows], require_terminal=True)
        self.assertTrue(strict(a, end)["terminal_verified"])
        self.assertFalse(strict(a)["all_supplied_records_usable"])
        self.assertFalse(strict(a, end, end)["terminal_verified"])
        self.assertFalse(strict(end, a)["terminal_verified"])
        for k, v in (("expected", 2), ("written", 0), ("complete", False),
                     ("code", 5), ("dropped_windows", 1), ("invalid_windows", True)):
            bad = dict(end, **{k: v})
            self.assertIsNone(strict(a, bad)["aggregate"])
        self.assertFalse(report(a)["terminal_verified"])

    def test_privacy_and_cli(self):
        a = window()
        a["private_path"] = "/private/synthetic-path"
        b = copy.deepcopy(a)
        b["sequence"] = 2
        b["spans"][0]["kind"] = "private-label"
        r = summarize([json.dumps(a), json.dumps(b), "private malformed sentinel"])
        self.assertIsNone(r["aggregate"])
        self.assertNotIn("private", json.dumps(r))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            path.write_text(json.dumps(a), encoding="utf-8")
            cmd = [sys.executable, str(Path(__file__).with_name("cpu_trace_report.py")), str(path)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn(directory, proc.stdout)
            self.assertNotIn("100000000", proc.stdout)
            path.write_text("private malformed sentinel", encoding="utf-8")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("private", proc.stdout)


if __name__ == "__main__":
    unittest.main()
