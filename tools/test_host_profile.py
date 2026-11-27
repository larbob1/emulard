# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys
import json
from pathlib import Path
import tempfile
import unittest

from host_profile import parse_stat, parse_io, read_snapshot, interval, sample, summarize


def stat(birth=20, user=100, system=50, rss=10):
    fields = ["S"] + ["0"] * 21
    for i, value in ((11, user), (12, system), (19, birth), (21, rss)):
        fields[i] = str(value)
    return "123 (private process ) with ( parentheses\n) " + " ".join(fields)


def snap(t=0, ticks=100, birth=20):
    return {"birth": birth, "ticks": ticks, "rss_pages": 10,
            "io": {"read_bytes": 20, "write_bytes": 30},
            "threads": {("private-thread", 1): ticks}, "threads_incomplete": False,
            "time_ns": t, "read_ns": 1000}


class HostProfileTests(unittest.TestCase):
    def test_stat_parentheses_and_units(self):
        self.assertEqual(parse_stat(stat()), (20, 150, 10))
        with self.assertRaises(ValueError):
            parse_stat("short")
        with self.assertRaises(ValueError):
            parse_stat(stat(user=-1))

    def test_io_schema(self):
        self.assertEqual(parse_io("rchar: 800\nread_bytes: 4\nwrite_bytes: 6\n"),
                         {"read_bytes": 4, "write_bytes": 6})
        for text in ("read_bytes: 4", "read_bytes: 1\nread_bytes: 2\nwrite_bytes: 3",
                     "read_bytes: -1\nwrite_bytes: 3"):
            with self.assertRaises(ValueError):
                parse_io(text)

    def test_snapshot_readonly_and_partial_threads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "123"
            task = proc / "task" / "456"
            task.mkdir(parents=True)
            (proc / "stat").write_text(stat())
            (task / "stat").write_text(stat())
            (proc / "task" / "789").mkdir()
            times = iter((100, 120, 300))
            r = read_snapshot(root, 123, lambda: next(times))
            self.assertEqual(r["time_ns"], 110)
            self.assertEqual(r["read_ns"], 200)
            self.assertIsNone(r["io"])
            self.assertTrue(r["threads_incomplete"])
            self.assertEqual(len(r["threads"]), 1)

    def test_cpu_and_optional_io(self):
        a, b = snap(), snap(2_000_000_000, 400)
        b["io"]["read_bytes"] += 400
        b["io"]["write_bytes"] += 200
        r = interval(a, b, 100, 4096)
        self.assertEqual(r["cpu_core_equivalents"], 1.5)
        self.assertEqual(r["rss_end_bytes"], 40960)
        self.assertEqual(r["read_bytes"], 400)
        self.assertEqual(r["hottest_stable_thread_core_equivalents"], 1.5)
        self.assertNotIn("private", json.dumps(r))
        b["io"]["read_bytes"] = 0
        b["threads_incomplete"] = True
        r = interval(a, b, 100, 4096)
        self.assertIsNone(r["read_bytes"])
        self.assertIsNone(r["hottest_stable_thread_core_equivalents"])

    def test_pid_reuse_and_counter_reset(self):
        for b in (snap(1_000_000_000, birth=21), snap(1_000_000_000, ticks=99), snap()):
            with self.assertRaises(ValueError):
                interval(snap(), b, 100, 4096)

    def test_thread_reuse_not_attributed(self):
        a, b = snap(), snap(1_000_000_000, 150)
        b["threads"] = {("private-thread", 2): 50}
        r = interval(a, b, 100, 4096)
        self.assertEqual(r["stable_threads"], 0)
        self.assertIsNone(r["hottest_stable_thread_core_equivalents"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "real /proc requires Linux")
    def test_live_own_process(self):
        result = sample(os.getpid(), 1, 0.25)
        self.assertTrue(result["complete"], result)
        self.assertGreater(result["elapsed_seconds"], 0)
        self.assertGreater(result["peak_sampled_rss_bytes"], 0)
        self.assertGreaterEqual(result["mean_cpu_core_equivalents"], 0)
        self.assertGreaterEqual(result["intervals"][0]["stable_threads"], 1)
        self.assertNotIn("birth", json.dumps(result))

    def test_elapsed_weighted_rates(self):
        a, b, c = snap(), snap(1_000_000_000, 200), snap(4_000_000_000, 800)
        c["io"] = None
        rows = [interval(a, b, 100, 4096), interval(b, c, 100, 4096)]
        result = summarize(rows, 2)
        self.assertEqual(result["mean_cpu_core_equivalents"], 1.75)
        self.assertEqual(result["io_observed_seconds"], 1)
        self.assertEqual(result["mean_observed_read_bytes_per_second"], 0)
        self.assertTrue(result["complete"])

    def test_capture_stops_on_unavailable_or_changed_process(self):
        snapshots = iter((snap(), snap(1_000_000_000, 200)))
        def reader(root, pid):
            try:
                return next(snapshots)
            except StopIteration:
                raise FileNotFoundError("private process")
        r = sample(123, 3, 1, reader=reader, sleeper=lambda _: None, hz=100, page_size=4096)
        self.assertFalse(r["complete"])
        self.assertEqual(r["completed_intervals"], 1)
        self.assertEqual(r["stop_reason"], "process_unavailable")
        self.assertNotIn("private process", json.dumps(r))
        self.assertNotIn("private-thread", json.dumps(r))
        snapshots = iter((snap(), snap(1_000_000_000, birth=21)))
        r = sample(123, 1, 1, reader=lambda *_: next(snapshots), sleeper=lambda _: None, hz=100, page_size=4096)
        self.assertEqual(r["completed_intervals"], 0)
        self.assertIsNone(r["mean_cpu_core_equivalents"])


if __name__ == "__main__":
    unittest.main()
