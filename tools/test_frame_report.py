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

    def test_missing_interval_but_individual_comparison(self):
        batch = "frame times: 2 frames in 0.1 s: shortest 40 ms, median 50, longest 60; 0 long (over 100 ms, the usual frame of the last 64 being 20); each: 40 60"
        report = summarize([batch])
        comparison = compare(report, report)
        self.assertEqual(comparison["approx_present_fps_ratio"], 1)
        self.assertIsNone(comparison["median_frame_speedup"])
        self.assertFalse(comparison["interval_comparison_usable"])
        self.assertTrue(comparison["individual_comparison_usable"])

    def test_invalid_samples_are_not_zero_or_speedup(self):
        bad = sample().replace("250 ms/frame", "nan ms/frame")
        report = summarize([sample(), bad, sample(0), sample(100)], skip=1)
        self.assertEqual(report["interval_sample_quality"],
                         {"seen": 4, "skipped": 1, "invalid_after_warmup": 2, "used": 1})
        self.assertIsNone(compare(report, report)["median_frame_speedup"])
        tiny = summarize([sample(0.0001)])
        self.assertEqual(compare(tiny, tiny)["median_frame_speedup"], 1)

    def test_invalid_frame_batch_suppresses_ratio(self):
        batch = "frame times: 2 frames in 0.1 s: shortest 40 ms, median 50, longest 60; 0 long (over 100 ms, the usual frame of the last 64 being 20); each: 40 60"
        report = summarize([sample(), batch, batch.replace("2 frames", "3 frames")])
        comparison = compare(report, report)
        self.assertEqual(comparison["median_frame_speedup"], 1)
        self.assertIsNone(comparison["approx_present_fps_ratio"])
        self.assertEqual(comparison["baseline_invalid_frame_batches"], 1)

    def test_critical_evidence_separate_populations_and_overlap(self):
        batch = "frame times: 3 frames in 0.5 s: shortest 20 ms, median 30, longest 450; 1 long (over 100 ms, the usual frame of the last 64 being 20); each: 20 30 450"
        detail = ("render thread: ran 30 ms (user 20, kernel 10); in the present call 40.0 "
                  "(lines and settling 30.0, copy and show 10.0), in submit calls 20.0, "
                  "in list calls 30.0, paced 5.0 | submit thread: at work 100.0 ms "
                  "(user 80.0, kernel 20.0); 4 submissions, preparing 200.0, waiting for "
                  "the card 150.0; copies 20.0 ms 5.0 MB; copy-back 25.0 ms 4.0 MB | "
                  "card: idle 10.0 ms (5.0 behind us); by its own clock, of the lists of a moment ago: "
                  "our send-and-hash lists 20.0 ms in 2, our compare lists 30.0 ms in 3, "
                  "all other lists 90.0 ms in 4 | remapping: 3 calls 300.0 ms (100.0 waiting for readers) | "
                  "disk: 10 reads 8.0 MB 600.0 worker ms")
        usual = "private usual frame (the mean of 2 not long): 25 ms | " + detail
        long = "private long frame 3 at 1.0 s: 450 ms | " + detail
        evidence = summarize([batch, usual, long, batch, usual.replace("8.0 MB", "4.0 MB")],
                             skip_frame_batches=0)["critical_path_evidence"]
        self.assertEqual(evidence["expected_usual_frames"], 4)
        self.assertEqual(evidence["represented_usual_frames"], 4)
        self.assertEqual(evidence["expected_long_frames_in_batches"], 2)
        self.assertEqual(evidence["listed_long_frame_records"], 1)
        u = evidence["usual_frame_cohort_means"]
        self.assertEqual(u["storage"]["destination_mb"]["weighted_mean"], 6)
        self.assertEqual(u["presenting_thread"]["present_settle_ms"]["weighted_mean"], 30)
        self.assertEqual(u["overlapping_work"]["remap_reader_wait_ms"]["weighted_mean"], 100)
        self.assertEqual(u["gpu_delayed"]["other_ms"]["weighted_mean"], 90)
        self.assertEqual(evidence["selected_long_frames"]["storage"]["worker_ms"]["max"], 600)
        self.assertEqual(evidence["critical_path_status"], "not attributable from aggregate counters")
        self.assertNotIn("private", str(evidence))
        skipped = summarize([batch, usual, long, batch, usual], skip_frame_batches=1)["critical_path_evidence"]
        self.assertEqual(skipped["represented_usual_frames"], 2)
        self.assertEqual(skipped["listed_long_frame_records"], 0)

    def test_critical_evidence_missing_fields_and_weighting(self):
        one = "frame times: 1 frames in 0.1 s: shortest 40 ms, median 40, longest 40; 0 long (over 100 ms, the usual frame of the last 64 being 20); each: 40"
        three = one.replace("1 frames", "3 frames").replace("each: 40", "each: 40 40 40")
        u1 = "usual frame (the mean of 1 not long): 40 ms | disk: 1 reads 4.0 MB 30.0 worker ms"
        u3 = "usual frame (the mean of 3 not long): 40 ms | disk: 3 reads 8.0 MB 60.0 worker ms"
        e = summarize([u1, one, u1, three, u3])["critical_path_evidence"]
        self.assertEqual(e["unanchored_detail_records"], 1)
        self.assertEqual(e["usual_frame_cohort_means"]["storage"]["destination_mb"],
                         {"records": 2, "represented_frames": 4, "weighted_mean": 7})
        self.assertEqual(e["usual_frame_cohort_means"]["gpu_delayed"], {})
        malformed = summarize([one.replace("1 frames", "2 frames"), u1])["critical_path_evidence"]
        self.assertEqual(malformed["represented_usual_frames"], 0)

    def test_duplicate_and_inconsistent_detail_records(self):
        batch = "frame times: 3 frames in 0.5 s: shortest 20 ms, median 150, longest 330; 2 long (over 100 ms, the usual frame of the last 64 being 20); each: 20 150 330"
        u = "usual frame (the mean of 1 not long): 20 ms | disk: 1 reads 4.0 MB 30.0 worker ms"
        long = "long frame 2 at 1.0 s: 150 ms | disk: 1 reads 8.0 MB 60.0 worker ms"
        e = summarize([batch, u.replace("1 not long", "2 not long"), u, u,
                       long, long, long.replace("frame 2", "frame 3"),
                       long.replace("frame 2", "frame 4")])["critical_path_evidence"]
        self.assertEqual(e["represented_usual_frames"], 1)
        self.assertEqual(e["listed_long_frame_records"], 2)
        self.assertEqual(e["rejected_detail_records"], 4)

    def test_hotpath_counters(self):
        result = summarize(["mapping diff run totals runs=4 pages=16", "texture view estimate hits hits=8"])
        self.assertEqual(result["latest_cumulative_counters"]["mapping diff run totals"]["pages"], 16)
        self.assertEqual(result["latest_cumulative_counters"]["texture view estimate hits"]["hits"], 8)

    def test_alias_direct_counters(self):
        result = summarize(["alias direct run totals attempts=2 hits=1", "alias direct run totals attempts=4 hits=3"])
        self.assertEqual(result["latest_cumulative_counters"]["alias direct run totals"], {"attempts": 4, "hits": 3})

    def test_scatter_lock_cumulative_quality(self):
        label = "scatter lock batch totals"
        lines = ["private scatter lock batch totals batches=1 pages=64 failures=0",
                 "scatter lock batch totals batches=2 pages=75 failures=1",
                 "scatter lock batch totals batches=4 pages=120",
                 "scatter lock batch totals batches=4 pages=1.5 failures=1",
                 "scatter lock batch totals batches=4 pages=120 pages=121 failures=1",
                 "scatter lock batch totals batches=1 pages=2 failures=0"]
        result = summarize(lines)
        self.assertEqual(result["latest_cumulative_counters"][label],
                         {"batches": 1, "pages": 2, "failures": 0})
        self.assertEqual(result["cumulative_counter_observations"][label],
                         {"valid_records": 3, "invalid_records": 3, "nonmonotonic_records": 1})
        self.assertNotIn("private", str(result))
        self.assertIn("not host syscalls", result["cumulative_counter_note"])

    def test_exact_placeholder_counter_quality(self):
        label = "exact placeholder totals"
        lines = ["private " + label + " attempts=4 hits=3",
                 label + " attempts=8 hits=7",
                 label + " attempts=16",
                 label + " attempts=16 hits=7.5"]
        report = summarize(lines)
        self.assertEqual(report["latest_cumulative_counters"][label],
                         {"attempts": 8, "hits": 7})
        self.assertEqual(report["cumulative_counter_observations"][label],
                         {"valid_records": 2, "invalid_records": 2, "nonmonotonic_records": 0})
        self.assertNotIn("private", str(report))

    def test_prefix_not_exported(self):
        self.assertNotIn("synthetic-prefix", str(summarize([sample()])))

class ShaderWarningTests(unittest.TestCase):
    def test_known_warning_separate_from_interval_drops(self):
        warning = "WARN private-synthetic-shader shader does not translate; its pipelines' draws are dropped error=private-detail"
        report = summarize([warning, sample(300), sample(30), warning,
                            "unrelated translation warning"], skip=1)
        self.assertEqual(report["intervals_with_dropped_draws"], 0)
        self.assertEqual(report["shader_translation_drop_warning_lines"], 2)
        self.assertNotIn("private-detail", str(report))
        self.assertEqual(summarize([warning])["shader_translation_drop_warning_lines"], 1)
        self.assertEqual(summarize([sample()])["shader_translation_drop_warning_lines"], 0)


class DirtyObservationTests(unittest.TestCase):
    def test_per_path_snapshots_and_noncoherent_fields(self):
        lines = ["private-prefix dirty_observe_v1 path=0 samples=1 bytes=10 chunks=2 unequal=3",
                 "dirty_observe_v1 path=1 samples=4096 bytes=268435456 chunks=65536 unequal=65536",
                 "dirty_observe_v1 path=0 samples=2 bytes=9 chunks=4 unequal=5",
                 sample()]
        result = summarize(lines, skip=1)
        observed = result["dirty_observation"]
        self.assertEqual(observed["message_lines"], 3)
        self.assertEqual(observed["invalid_records"], 0)
        self.assertEqual(observed["paths"]["0"], {
            "valid_records": 2, "descending_records": 1,
            "latest": {"samples": 2, "bytes": 9, "chunks": 4, "unequal": 5}})
        self.assertEqual(observed["paths"]["1"]["valid_records"], 1)
        self.assertNotIn("2", observed["paths"])
        self.assertNotIn("private-prefix", str(result))
        self.assertEqual(summarize([])["dirty_observation"]["paths"], {})

    def test_invalid_payloads_are_counted_without_exporting(self):
        valid = "dirty_observe_v1 path=0 samples=1 bytes=2 chunks=1 unequal=1"
        bad = [valid.replace("path=0", "path=3"),
               valid.replace("samples=1", "samples=4097"),
               valid.replace("bytes=2", "bytes=268435457"),
               valid.replace("chunks=1", "chunks=65537"),
               valid.replace("unequal=1", "unequal=65537"),
               valid.replace("bytes=2", "bytes=-2"),
               valid.replace("bytes=2", "bytes=2.0"),
               valid.replace("bytes=2", "bytes=12345678901234567890"),
               valid.replace("bytes=2", "bytes=2 bytes=3"),
               valid.replace(" bytes=2", ""),
               valid + " secret=private-payload", valid + " " + valid]
        result = summarize(bad + [valid, "not_dirty_observe_v1 "])
        self.assertEqual(result["dirty_observation"]["message_lines"], len(bad) + 1)
        self.assertEqual(result["dirty_observation"]["invalid_records"], len(bad))
        self.assertEqual(result["dirty_observation"]["paths"]["0"]["valid_records"], 1)
        self.assertNotIn("private-payload", str(result))


if __name__ == "__main__":
    unittest.main()
