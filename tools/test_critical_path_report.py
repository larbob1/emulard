# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from critical_path_report import analyze, summarize, union_length


def span(i, a, b, kind, deps=()):
    return {"id": i, "start_us": a, "end_us": b, "kind": kind, "depends_on": list(deps)}


def fixture():
    return {"schema": 1, "frame": 9, "clock": "host_monotonic_calibrated",
            "complete": True, "lost_spans": 0, "start_us": 0, "end_us": 100,
            "terminal": 4, "spans": [
                span(1, 0, 40, "mapping"),
                span(2, 10, 60, "gpu"),
                span(3, 60, 80, "cpu_submit", (1, 2)),
                span(4, 90, 100, "present", (3,)),
                span(5, 0, 90, "storage"),
            ]}


class CriticalPathTests(unittest.TestCase):
    def test_parallel_join_and_unrelated_worker(self):
        r = analyze(fixture())
        self.assertEqual(r["longest_measured_dependency_chain_us"], 80)
        self.assertEqual(r["terminal_ancestor_union_us"], 90)
        self.assertEqual(r["terminal_ancestor_aggregate_us"], 120)
        self.assertEqual(r["terminal_ancestor_overlap_excess_us"], 30)
        self.assertEqual(r["all_span_union_us"], 100)
        self.assertEqual(r["unrelated_span_count"], 1)
        self.assertEqual(r["wall_us_outside_selected_chain_work"], 20)
        self.assertEqual(r["chain_category_us"], {"cpu_submit": 20, "gpu": 50, "present": 10})

    def test_serial_chain(self):
        f = fixture()
        f["spans"] = [span(1, 0, 40, "mapping"),
                      span(2, 40, 80, "gpu", (1,)),
                      span(4, 80, 100, "present", (2,))]
        r = analyze(f)
        self.assertEqual(r["longest_measured_dependency_chain_us"], 100)
        self.assertEqual(r["wall_us_outside_selected_chain_work"], 0)
        self.assertEqual(r["terminal_ancestor_overlap_excess_us"], 0)

    def test_tie_not_arbitrarily_attributed(self):
        f = fixture()
        f["spans"][1]["start_us"] = 20
        r = analyze(f)
        self.assertTrue(r["equal_length_chain_ambiguity"])
        self.assertIsNone(r["chain_category_us"])
        self.assertEqual(r["longest_measured_dependency_chain_us"], 70)

    def test_bad_edges_or_nested_waits(self):
        for change, reason in (
                (lambda f: f["spans"][2].update(depends_on=[123]), "missing_dependency"),
                (lambda f: f["spans"][2].update(start_us=59), "overlapping_or_reversed_dependency"),
                (lambda f: f["spans"][2].update(depends_on=[3]), "duplicate_or_self_dependency"),
                (lambda f: f["spans"][2].update(depends_on=[1, 1]), "duplicate_or_self_dependency")):
            f = fixture()
            change(f)
            with self.assertRaisesRegex(ValueError, reason):
                analyze(f)

    def test_invalid_window_kind_terminal_and_id(self):
        for change in (
                lambda f: f["spans"][0].update(start_us=-1),
                lambda f: f["spans"][0].update(end_us=0),
                lambda f: f["spans"][0].update(kind=["private"]),
                lambda f: f["spans"][0].update(id=True),
                lambda f: f["spans"][0].update(id=2),
                lambda f: f.update(terminal=5)):
            f = fixture()
            change(f)
            with self.assertRaises(ValueError):
                analyze(f)

    def test_clock_loss_and_incomplete(self):
        for key, value in (("clock", "gpu_raw"), ("complete", False), ("lost_spans", 1)):
            f = fixture()
            f[key] = value
            r = analyze(f)
            self.assertEqual(r["status"], "insufficient_evidence")
            self.assertNotIn("longest_measured_dependency_chain_us", r)

    def test_record_quality_and_privacy(self):
        a = fixture()
        a["private_path"] = "/secret/game"
        b = copy.deepcopy(a)
        b["frame"] = 10
        b["spans"][0]["kind"] = "secret-label"
        report = summarize([json.dumps(a), json.dumps(a), json.dumps(b), "private malformed data"])
        self.assertEqual(report["valid_frames"], 1)
        self.assertEqual(report["rejected_frames"], 3)
        self.assertFalse(report["all_records_usable"])
        self.assertIsNone(report["median_measured_chain_us"])
        self.assertNotIn("secret", json.dumps(report))
        self.assertNotIn("private", json.dumps(report))

    def test_contiguous_capture_and_missing_frames(self):
        first = fixture()
        second = copy.deepcopy(first)
        second["frame"] += 1
        for key in ("start_us", "end_us"):
            second[key] += 100
            for node in second["spans"]:
                node[key] += 100
        def report():
            return summarize([json.dumps(first), json.dumps(second)])
        self.assertTrue(report()["all_records_usable"])
        second["frame"] += 1
        r = report()
        self.assertEqual(r["sequence_issues"], {"nonconsecutive_frame_ids": 1})
        self.assertIsNone(r["median_measured_chain_us"])
        second["frame"] -= 1
        second["start_us"] -= 1
        self.assertEqual(report()["sequence_issues"], {"discontinuous_frame_windows": 1})
        self.assertFalse(report()["all_records_usable"])

    def test_boolean_schema_rejected(self):
        f = fixture()
        f["schema"] = True
        with self.assertRaisesRegex(ValueError, "invalid_schema"):
            analyze(f)

    def test_union_and_empty(self):
        self.assertEqual(union_length([(0, 10), (2, 3), (10, 20), (25, 30)]), 25)
        self.assertEqual(union_length([]), 0)
        self.assertFalse(summarize([])["all_records_usable"])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "private-trace.jsonl"
            p.write_text(json.dumps(fixture()), encoding="utf-8")
            cmd = [sys.executable, str(Path(__file__).with_name("critical_path_report.py")), str(p)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn(directory, proc.stdout)
            self.assertEqual(json.loads(proc.stdout)["median_measured_chain_us"], 80)
            p.write_text("private malformed", encoding="utf-8")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("private", proc.stdout)


if __name__ == "__main__":
    unittest.main()
