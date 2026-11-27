# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from storage_scratch_report import summarize


def fixture():
    # Synthetic valid arithmetic, not captured benchmark results.
    cases = (("disabled", 0, 120, 0, 2458368, 0),
             ("bounded", 65536, 60, 15, 2000000, 65536),
             ("cap4k", 4096, 90, 0, 2300000, 4096),
             ("cap8k", 8192, 80, 5, 2200000, 8192),
             ("cap16k", 16384, 80, 5, 2200000, 8192),
             ("cap32k", 32768, 70, 8, 2100000, 32768),
             ("cap128k", 131072, 50, 20, 1950000, 131072))
    return [
        f"Storage scratch mixed calls: mode={mode} cap={cap} requests=128"
        f" failed=16 nonzero=120 input_bytes=2458368 baseline_acquisitions=120"
        f" baseline_requested=2458368 reuse_acquisitions={calls} reuse_realloc={realloc}"
        f" reuse_requested={requested} reuse_dealloc={calls-realloc} hits={120-calls}"
        f" trim_events=9 peak_idle={peak} final_idle=0"
        for mode, cap, calls, realloc, requested, peak in cases
    ]


class ScratchReceiptTests(unittest.TestCase):
    def test_complete(self):
        result = summarize(fixture())
        self.assertTrue(result["valid"])
        self.assertFalse(result["provenance_verified"])
        self.assertEqual(result["valid_rows"], 7)
        self.assertEqual(result["cases"][1]["acquisition_calls_saved"], 60)
        self.assertEqual(result["cases"][1]["requested_size_difference_bytes"], -458368)

    def test_missing_duplicate_order(self):
        rows = fixture()
        for altered in (rows[:-1], rows + rows[:1], rows[::-1], []):
            result = summarize(altered)
            self.assertFalse(result["valid"])
            self.assertEqual(result["cases"], [])

    def test_field_failures(self):
        for addition in (" hits=0", " secret=private", " broken", " cap=0"):
            rows = fixture()
            rows[0] += addition
            result = summarize(rows)
            self.assertFalse(result["valid"])
            self.assertNotIn("private", str(result))
        rows = fixture()
        rows[0] = rows[0].replace(" final_idle=0", "")
        self.assertFalse(summarize(rows)["valid"])

    def test_bad_counts_and_balance(self):
        for old, new in (("failed=16", "failed=17"), ("requests=128", "requests=127"),
                         ("hits=60", "hits=61"), ("reuse_realloc=15", "reuse_realloc=61"),
                         ("reuse_dealloc=45", "reuse_dealloc=44"),
                         ("peak_idle=65536", "peak_idle=65537"),
                         ("final_idle=0", "final_idle=1"), ("trim_events=9", "trim_events=8")):
            rows = fixture()
            rows[1] = rows[1].replace(old, new)
            result = summarize(rows)
            self.assertFalse(result["valid"])
            self.assertEqual(result["errors"]["inconsistent"], 1)

    def test_disabled_parity_and_numeric_bounds(self):
        for old, new in (("reuse_requested=2458368", "reuse_requested=2458369"),
                         ("reuse_requested=2458368", "reuse_requested=-1"),
                         ("reuse_requested=2458368", "reuse_requested=18446744073709551616"),
                         ("reuse_requested=2458368", "reuse_requested=1e9")):
            rows = fixture()
            rows[0] = rows[0].replace(old, new)
            self.assertFalse(summarize(rows)["valid"])

    def test_no_forced_gain_other_caps(self):
        rows = fixture()
        rows[2] = (rows[2].replace("reuse_acquisitions=90", "reuse_acquisitions=120")
                   .replace("reuse_dealloc=90", "reuse_dealloc=120")
                   .replace("hits=30", "hits=0"))
        self.assertTrue(summarize(rows)["valid"])


if __name__ == "__main__":
    unittest.main()
