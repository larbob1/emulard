# SPDX-License-Identifier: GPL-3.0-or-later
import json
import unittest

from memory_report import summarize, SCHEMAS, compare_grids


def memory(private=2566, working=3637, copies=7, capacity=202, made=10):
    return (f"private-prefix memory: {private} MB private ({working} MB of it in memory; the PC has 5000 MB free and 6000 MB left to commit); "
            f"host copies of title memory: {copies} alive {capacity} MB, of them 6 windows outside buffers 28 MB; snapshot buffers kept: 0 reserving 0 MB; "
            f"staging of textures: 20 alive 342 MB, 10 kept by their texture; host textures: 50 alive 2421 MB, 25 placed in title memory; "
            f"made so far: {made} upload buffers 100 MB, 50 shared buffers 202 MB, 25 card buffers 250 MB")


HOLDERS = ("memory, what holds it: 12 host lists alive; their scratch memory: 4 chunks 9 MB, of          them 2 chunks 2 MB spare (3 taken from the spare ones so far); "
           "their other upload          buffers: 5 alive 8 MB; windows outside buffers (grid 4096 KiB): 100 MB of their          pages ever copied, "
           "20 shown by descriptor slots 80 MB, 15 held by lists or the pass          over the heap 60 MB, 3 asked for without a length 12 MB; "
           "buffer views of the heap          whose slot showed another copy than the one brought up to date: 2; distinct views          kept: 25 (5 free) 1 MB; "
           "our own allocations: 10 MB in 20 blocks (under 4 KiB          1 MB in 5, to 64 KiB 2 MB in 5, to 1 MiB 3 MB in 5, larger 4 MB in 5)")


class MemoryReportTests(unittest.TestCase):
    def test_transition_and_independent_groups(self):
        result = summarize([memory(), HOLDERS,
                            memory(3191, 12430, 4120, 3703, 20)])
        groups = result["groups"]
        m = groups["memory"]["metrics"]
        self.assertEqual(m["working_set_mib"]["endpoint_change"], 8793)
        self.assertEqual(m["host_copy_mib"]["endpoint_change"], 3501)
        self.assertEqual(m["host_copies"]["endpoint_change"], 4113)
        self.assertEqual(m["working_set_mib"]["last_line"], 3)
        self.assertEqual(groups["holders"]["metrics"]["windows_in_slots_mib"]["last"], 80)
        self.assertEqual(groups["holders"]["metrics"]["windows_in_lists_mib"]["last"], 60)
        self.assertEqual(groups["coverage"]["valid_records"], 0)
        self.assertNotIn("private-prefix", json.dumps(result))

    def test_coverage_and_shader_cache(self):
        result = summarize(["memory, windows: the 3000 MB of windows lie over 2000 MB of title memory (the rest is memory that is in more than one window, and is copied once for each); host lists never reset since they were made: 9",
                            "memory kept beside the lines below: 1 shader containers 2 MB, 3 translations 4 MB; the pipeline library's file 5 MB (its last save wrote 6 MB)"])
        groups = result["groups"]
        self.assertEqual(groups["coverage"]["metrics"]["title_window_coverage_mib"]["last"], 2000)
        self.assertEqual(groups["shader_cache"]["metrics"]["last_save_mib"]["last"], 6)
        self.assertEqual(groups["memory"]["metrics"], {})

    def test_malformed_duplicate_overflow_and_unrelated(self):
        result = summarize([memory(), memory().replace("3637", "-1"),
                            memory() + " " + memory(),
                            memory().replace("3637", "18446744073709551616"),
                            "video memory: 100 MB in use", "memory, what holds it: malformed private-secret"])
        groups = result["groups"]
        self.assertEqual(groups["memory"]["valid_records"], 1)
        self.assertEqual(groups["memory"]["invalid_records"], 3)
        self.assertEqual(groups["holders"]["invalid_records"], 1)
        self.assertNotIn("private-secret", json.dumps(result))

    def test_truncated_bare_primary_record_is_an_invalid_gap(self):
        group = summarize([memory(), "memory: 123 MB",
                           "  memory:", "memory: malformed",
                           "video memory: 100 MB in use",
                           "host copies of title memory: 2 alive 3 MB",
                           memory(made=11)])["groups"]["memory"]
        self.assertEqual(group["valid_records"], 2)
        self.assertEqual(group["invalid_records"], 3)
        rows = group["recent_observations"]
        self.assertEqual([r["line"] for r in rows], [1, 2, 3, 4, 7])
        self.assertEqual(rows[-1]["change_status"], "prior_record_invalid")
        self.assertIsNone(rows[-1]["adjacent_change"])

    def test_sweep_and_asked_spans_have_distinct_semantics(self):
        def sweep(n, mb, asked):
            return (f"memory let go since the start: {n} windows outside buffers {mb} MB, "
                    f"2 staging buffers 8 MB; of the windows alive, {asked} MB lie between "
                    "the lowest and highest address asked for in each")
        result = summarize([sweep(1, 4, 8), sweep(3, 16, 1231),
                            sweep(3, 16, 1000), sweep(2, 12, 900),
                            "memory let go since the start: private-malformed"])
        g = result["groups"]["sweep"]
        self.assertEqual(g["valid_records"], 4)
        self.assertEqual(g["invalid_records"], 1)
        self.assertEqual(g["descending_cumulative_records"], 1)
        self.assertEqual(g["metrics"]["window_asked_span_mib"]["max"], 1231)
        self.assertEqual(g["metrics"]["windows_released"]["endpoint_change"], 1)
        self.assertNotIn("private-malformed", json.dumps(result))
        self.assertEqual(summarize([memory()])["groups"]["sweep"]["metrics"], {})

    def test_recent_observations_preserve_invalid_gap(self):
        result = summarize([memory(), HOLDERS, memory().replace("3637", "-1"),
                            memory(3191, 12430, 4120, 3703, 20),
                            memory(3200, 12431, 4121, 3704, 21)])
        rows = result["groups"]["memory"]["recent_observations"]
        self.assertEqual([r["line"] for r in rows], [1, 3, 4, 5])
        self.assertIsNone(rows[1]["values"])
        self.assertIsNone(rows[2]["adjacent_change"])
        self.assertEqual(rows[2]["change_status"], "prior_record_invalid")
        self.assertEqual(rows[3]["adjacent_change"]["working_set_mib"], 1)
        self.assertNotIn("private-prefix", json.dumps(result))

    def test_recent_tail_is_bounded_and_never_references_evicted_row(self):
        group = summarize(memory(made=n) for n in range(10))["groups"]["memory"]
        rows = group["recent_observations"]
        self.assertEqual([r["line"] for r in rows], [6, 7, 8, 9, 10])
        self.assertIsNone(rows[0]["adjacent_change"])
        self.assertEqual(rows[0]["change_status"], "prior_outside_tail")
        self.assertEqual(rows[-1]["adjacent_change"]["upload_made"], 1)
        self.assertEqual(group["valid_records"], 10)

    def test_recent_counter_reset_and_grid_change_suppress_delta(self):
        rows = summarize([memory(made=10), memory(made=9), memory(made=11)]
                         )["groups"]["memory"]["recent_observations"]
        self.assertEqual(rows[1]["change_status"], "descending_cumulative")
        self.assertIsNone(rows[1]["adjacent_change"])
        self.assertEqual(rows[2]["adjacent_change"]["upload_made"], 2)
        rows = summarize([HOLDERS, HOLDERS.replace("4096 KiB", "2048 KiB")]
                         )["groups"]["holders"]["recent_observations"]
        self.assertEqual(rows[-1]["change_status"], "grid_changed")
        self.assertIsNone(rows[-1]["adjacent_change"])

    def test_cumulative_decrease_does_not_hide_latest(self):
        group = summarize([memory(made=10), memory(made=9)])["groups"]["memory"]
        self.assertEqual(group["descending_cumulative_records"], 1)
        self.assertEqual(group["metrics"]["upload_made"]["endpoint_change"], -1)


class GridComparisonTests(unittest.TestCase):
    def reports(self):
        coverage = "memory, windows: the 3000 MB of windows lie over 2000 MB of title memory (the rest is memory that is in more than one window, and is copied once for each); host lists never reset since they were made: 9"
        a = summarize([memory(), HOLDERS, coverage])
        b = summarize([memory(capacity=150), HOLDERS.replace("4096 KiB", "2048 KiB"), coverage])
        return a,b

    def test_requires_operator_confirmation(self):
        a,b = self.reports()
        self.assertFalse(compare_grids(a,b)["comparison_usable"])
        result = compare_grids(a,b,True)
        self.assertTrue(result["comparison_usable"])
        self.assertEqual(result["groups"]["memory"]["fields"]["host_copy_mib"]["last_difference"], -52)
        self.assertFalse(result["groups"]["sweep"]["comparison_usable"])
        self.assertEqual(result["groups"]["sweep"]["fields"], {})

    def test_nonboolean_confirmation_does_not_certify_grid_comparison(self):
        a, b = self.reports()
        for confirmed in (1, "yes", "false", [True], None):
            with self.subTest(confirmed=confirmed):
                result = compare_grids(a, b, confirmed)
                self.assertFalse(result["operator_confirmed_matched_completed_phase"])
                self.assertFalse(result["comparison_usable"])
                self.assertEqual(result["groups"]["memory"]["fields"], {})

    def test_truncated_primary_record_blocks_grid_comparison(self):
        a, b = self.reports()
        coverage = "memory, windows: the 3000 MB of windows lie over 2000 MB of title memory (the rest is memory that is in more than one window, and is copied once for each); host lists never reset since they were made: 9"
        b = summarize([memory(), "memory: 123 MB",
                       HOLDERS.replace("4096 KiB", "2048 KiB"), coverage])
        result = compare_grids(a, b, True)
        self.assertFalse(result["comparison_usable"])
        self.assertIn("candidate_primary_or_coverage_evidence_invalid_or_missing",
                      result["issues"])

    def test_mixed_wrong_missing_and_invalid_grid(self):
        a,b = self.reports()
        self.assertFalse(compare_grids(a,a,True)["comparison_usable"])
        for bad in (summarize([memory()]),
                    summarize([memory(), HOLDERS.replace("4096 KiB", "3000 KiB")]),
                    summarize([memory(), HOLDERS, HOLDERS.replace("4096 KiB", "2048 KiB")])):
            self.assertFalse(compare_grids(a,bad,True)["comparison_usable"])
        self.assertEqual(summarize([HOLDERS.replace("4096 KiB", "3000 KiB")])["groups"]["holders"]["invalid_records"], 1)
        self.assertEqual(summarize([HOLDERS, HOLDERS.replace("4096 KiB", "2048 KiB")])["observed_window_grids_kib"], [2048,4096])

    def test_missing_coverage_and_invalid_record_refuse_comparison(self):
        a,b = self.reports()
        b["groups"]["coverage"]["valid_records"] = 0
        self.assertFalse(compare_grids(a,b,True)["comparison_usable"])
        a,b = self.reports()
        b["groups"]["holders"]["invalid_records"] = 1
        result = compare_grids(a,b,True)
        self.assertFalse(result["comparison_usable"])
        self.assertEqual(result["groups"]["memory"]["fields"], {})


if __name__ == "__main__":
    unittest.main()
