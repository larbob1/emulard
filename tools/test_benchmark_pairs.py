# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
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

    def test_empty_input(self):
        with self.assertRaises(ValueError):
            aggregate([])
        with self.assertRaises(ValueError):
            aggregate([(summarize([]), summarize([sample()]))])

if __name__ == "__main__":
    unittest.main()
