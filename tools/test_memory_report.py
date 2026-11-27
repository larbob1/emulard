# SPDX-License-Identifier: GPL-3.0-or-later
import json
import unittest

from memory_report import summarize, SCHEMAS


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

    def test_cumulative_decrease_does_not_hide_latest(self):
        group = summarize([memory(made=10), memory(made=9)])["groups"]["memory"]
        self.assertEqual(group["descending_cumulative_records"], 1)
        self.assertEqual(group["metrics"]["upload_made"]["endpoint_change"], -1)


if __name__ == "__main__":
    unittest.main()
