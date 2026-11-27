# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from benchmark_pairs import aggregate
from frame_report import summarize
from test_frame_report import sample

class BenchmarkPairsTests(unittest.TestCase):
    def test_pairs(self):
        a = summarize([sample(300)])
        b = summarize([sample(150)])
        c = summarize([sample(300, 1)])
        result = aggregate([(a,b),(a,b),(a,c)])
        self.assertEqual(result["median_paired_speedup"], 2)
        self.assertEqual(result["candidate_faster_pairs"], 2)
        self.assertEqual(result["candidate_pairs_with_reported_drops"], 1)
        self.assertTrue(result["at_least_three_pairs"])
        self.assertFalse(result["operator_reported_visible_scene"])
        self.assertNotIn("synthetic-prefix", str(result))

    def test_partial_pairs_and_independent_frame_tails(self):
        batch = "frame times: 2 frames in 0.1 s: shortest 40 ms, median 50, longest 60; 0 long (over 100 ms, the usual frame of the last 64 being 20); each: 40 60"
        a = summarize([sample(300), sample(300, 1), batch])
        b = summarize([sample(150), batch])
        frames_only = summarize([batch])
        result = aggregate([(a, b), (frames_only, frames_only), (summarize([]), b)])
        self.assertEqual(result["usable_interval_pairs"], 1)
        self.assertEqual(result["usable_individual_pairs"], 2)
        self.assertEqual(result["incomplete_pairs"], 2)
        self.assertEqual(result["median_paired_speedup"], 2)
        self.assertEqual(result["median_paired_approx_present_fps_ratio"], 1)
        self.assertEqual(result["runs"][0]["baseline_drop_interval_fraction"], 0.5)
        self.assertEqual(result["runs"][1]["baseline_individual"]["frame_ms_percentiles"]["p99"], 60)
        self.assertIsNone(result["runs"][2]["speedup"])
        self.assertFalse(result["at_least_three_usable_interval_pairs"])
        self.assertEqual(result["candidate_pairs_with_unknown_drops"], 1)

    def test_cli_warmup_and_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = (Path(directory) / name for name in ("private-a.log", "private-b.log"))
            batch = "frame times: 2 frames in 0.1 s: shortest 40 ms, median 50, longest 60; 0 long (over 100 ms, the usual frame of the last 64 being 20); each: 40 60"
            a.write_text("\n".join([sample(), batch, sample(), batch]), encoding="utf-8")
            b.write_text("\n".join([sample(150), batch, sample(150), batch]), encoding="utf-8")
            command = [sys.executable, str(Path(__file__).with_name("benchmark_pairs.py")),
                       "--skip", "1", "--skip-frame-batches", "1", "--target-fps", "30"]
            proc = subprocess.run(command + ["--pair", str(a), str(b)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["runs"][0]["baseline_intervals"], 1)
            self.assertEqual(result["runs"][0]["baseline_individual"]["samples"], 2)
            self.assertNotIn(directory, proc.stdout)
            self.assertEqual(result["distinct_normalized_log_contents"], 2)
            self.assertFalse(result["independent_trials_verified"])
            self.assertFalse(result["matched_workload_verified"])
            duplicate = subprocess.run(command + ["--pair", str(a), str(a)], capture_output=True, text=True)
            self.assertEqual(duplicate.returncode, 1)
            self.assertNotIn(directory, duplicate.stdout)

    def test_cli_copied_contents_across_pairs_and_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b, c, d = (Path(directory) / name for name in ("a.log", "b.log", "c.log", "d.log"))
            a.write_bytes((sample(300) + "\n").encode())
            b.write_bytes((sample(150) + "\n").encode())
            c.write_bytes((sample(300) + "\r\n").encode())
            d.write_bytes((sample(100) + "\n").encode())
            cmd = [sys.executable, str(Path(__file__).with_name("benchmark_pairs.py")), "--skip", "0"]
            for pairs in (["--pair", str(a), str(c)],
                          ["--pair", str(a), str(b), "--pair", str(c), str(d)]):
                proc = subprocess.run(cmd + pairs, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(json.loads(proc.stdout)["reason"], "repeated_log_content")
                self.assertNotIn(directory, proc.stdout)
            c.write_bytes(sample(300).encode())  # no final newline
            proc = subprocess.run(cmd + ["--pair", str(a), str(c)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["reason"], "repeated_log_content")
            c.write_bytes((sample(220) + "\n").encode())
            proc = subprocess.run(cmd + ["--pair", str(a), str(b), "--pair", str(c), str(d)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["distinct_normalized_log_contents"], 4)

    def test_pairs_preserve_scatter_counter_observations(self):
        label = "scatter lock batch totals"
        a = summarize([sample()])
        b = summarize([sample(), label + " batches=2 pages=70 failures=0"])
        row = aggregate([(a, b)])["runs"][0]
        self.assertNotIn(label, row["baseline_latest_cumulative_counters"])
        self.assertEqual(row["candidate_latest_cumulative_counters"][label]["pages"], 70)
        self.assertEqual(row["candidate_cumulative_counter_observations"][label]["valid_records"], 1)

    def test_pairs_preserve_exact_placeholder_counter(self):
        label = "exact placeholder totals"
        a = summarize([sample()])
        b = summarize([sample(), label + " attempts=8 hits=7"])
        row = aggregate([(a, b)])["runs"][0]
        self.assertNotIn(label, row["baseline_latest_cumulative_counters"])
        self.assertEqual(row["candidate_latest_cumulative_counters"][label],
                         {"attempts": 8, "hits": 7})

    def test_empty_input(self):
        with self.assertRaises(ValueError):
            aggregate([])
        with self.assertRaises(ValueError):
            aggregate([(summarize([]), summarize([sample()]))])

if __name__ == "__main__":
    unittest.main()
