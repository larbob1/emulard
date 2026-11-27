# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from frame_report import summarize, compare

def sample(frame=250, dropped=0):
    return (f"synthetic-prefix 4.0 fps, {frame} ms/frame "
            "(80.0 preparing: copies 20.0 ms 8.0 MB, textures 10.0 ms 4.0 MB; "
            f"120.0 on the GPU; 20.0 copying back 2.0 MB), 100 draws/frame, "
            f"dropped {dropped} without a host pipeline (0 being made)")

class FrameReportTests(unittest.TestCase):
    def test_frame_budget(self):
        report = summarize([sample(250), sample(100)])
        self.assertEqual(report["samples"], 2)
        self.assertEqual(report["median_reported_interval"]["frame"], 175)
        self.assertEqual(report["frame_ms_above_target"], 75)
        self.assertEqual(report["intervals_at_or_below_target"], 1)

    def test_compare_workloads(self):
        result = compare(summarize([sample(250)]), summarize([sample(100)]))
        self.assertEqual(result["median_frame_ms_delta"], -150)
        self.assertEqual(result["median_frame_speedup"], 2.5)
        self.assertEqual(result["median_copy_back_mb_delta"], 0)
        self.assertEqual(result["candidate_clean_target_intervals"], 1)
        self.assertEqual(compare(summarize([]), summarize([sample()]))["status"], "insufficient samples")

    def test_fast_but_incomplete_is_not_clean(self):
        self.assertEqual(summarize([sample(90, 1)])["intervals_meeting_target_without_reported_drops"], 0)

    def test_dropped_draws_not_hidden(self):
        self.assertEqual(summarize([sample(100, 10)])["intervals_with_dropped_draws"], 1)

    def test_skip_and_ignore_unknown(self):
        self.assertEqual(summarize([sample(), "unknown", sample(100)], 1)["samples"], 1)

    def test_empty_and_zero(self):
        self.assertEqual(summarize(["unknown", sample(0)])["samples"], 0)

    def test_long_frame_telemetry_separate_from_intervals(self):
        line = ("private prefix textures: refresh 450.0 ms (400.0 waiting for memory to hold still), "
                "remapping: 50 calls 500.0 ms (20.0 waiting for readers; of it the system's "
                "unmapping 100.0, its mapping 350.0, committing 0.0, our own notes of the change "
                "30.0; 3 views cut, 1.0 MB of them mapped again; 10 placeholders reused, 0 reuse fallbacks)")
        alias = ("page mappings of the title's queues per second: 5 calls for 20 pages, "
                 "10 of them as they were, 4 views mapped, 8.0 ms")
        result = summarize([sample(), line, alias])
        self.assertEqual(result["samples"], 1)
        self.assertEqual(result["long_frame_samples"], 1)
        self.assertEqual(result["long_frame_remapping"]["map_ms"]["median"], 350)
        self.assertEqual(result["long_frame_remapping"]["refresh_wait_ms"]["median"], 400)
        self.assertEqual(result["alias_rates_per_second"]["same"]["median"], 10)
        self.assertNotIn("private prefix", str(result))
        self.assertEqual(summarize([line])["long_frame_samples"], 1)

    def test_interval_percentiles_and_milestones(self):
        report = summarize([sample(20), sample(50), sample(100, 1), sample(300),
                            "long frame 3 at 3.0 s: 400 ms | other details",
                            "long frames: 4 more in this reading are not listed"])
        self.assertEqual(report["reported_interval_frame_ms_percentiles"]["p95"], 300)
        self.assertEqual(report["fps_milestones"]["20"]["intervals"], 2)
        self.assertEqual(report["fps_milestones"]["10"]["without_reported_drops_or_pending"], 2)
        self.assertEqual(report["reported_long_frames"]["max_ms"], 400)
        self.assertEqual(report["reported_long_frames"]["omitted_count"], 4)

    def test_cumulative_counters_not_summed(self):
        report = summarize([sample(), "private mapping diff totals calls=2 saved=10 mapped=3 scatter=4",
                            "mapping diff totals calls=4 saved=17 mapped=6 scatter=7",
                            "texture short-lock totals calls=8 bytes=512 copy_us=30 unlocked_us=90 retries=1",
                            "unchanged physical mapping requests skipped count=16"])
        counts = report["latest_cumulative_counters"]
        self.assertEqual(counts["mapping diff totals"]["saved"], 17)
        self.assertEqual(counts["texture short-lock totals"]["retries"], 1)
        self.assertEqual(counts["unchanged physical mapping requests skipped"]["count"], 16)
        self.assertNotIn("private", str(report))

    def test_actual_frame_batches(self):
        line = "private frame times: 4 frames in 0.5 s: shortest 10 ms, median 30, longest 400; 1 long (over 100 ms, the usual frame of the last 64 being 20); each: 10 20 40 400"
        bad = line.replace("4 frames", "5 frames")
        result = summarize([line, bad, line, sample()], skip_frame_batches=1)
        actual = result["individual_frame_times"]
        self.assertEqual(actual["samples"], 4)
        self.assertEqual(actual["batches_skipped"], 1)
        self.assertEqual(actual["invalid_batches"], 1)
        self.assertEqual(actual["frame_ms_percentiles"]["p95"], 400)
        self.assertEqual(actual["frame_ms_percentiles"]["p50"], 20)
        self.assertNotIn("private", str(result))

    def test_30_fps_budget_and_actual_present_rate(self):
        batch = "frame times: 3 frames in 0.1 s: shortest 10 ms, median 30, longest 60; 0 long (over 100 ms, the usual frame of the last 64 being 20); each: 10 30 60"
        report = summarize([sample(33), sample(34), sample(20, 1), batch], target_fps=30)
        self.assertAlmostEqual(report["target_frame_ms"], 1000 / 30, places=5)
        self.assertEqual(report["intervals_at_or_below_target"], 2)
        self.assertEqual(report["intervals_meeting_target_without_reported_drops"], 1)
        actual = report["individual_frame_times"]
        self.assertEqual(actual["approx_present_fps"], 30)
        self.assertEqual(actual["frames_within_target_ms"], 2)
        self.assertEqual(compare(report, report)["approx_present_fps_ratio"], 1)
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                summarize([], target_fps=value)

    def test_hotpath_counters(self):
        result = summarize(["mapping diff run totals runs=4 pages=16", "texture view estimate hits hits=8"])
        self.assertEqual(result["latest_cumulative_counters"]["mapping diff run totals"]["pages"], 16)
        self.assertEqual(result["latest_cumulative_counters"]["texture view estimate hits"]["hits"], 8)

    def test_prefix_not_exported(self):
        self.assertNotIn("synthetic-prefix", str(summarize([sample()])))

if __name__ == "__main__":
    unittest.main()
