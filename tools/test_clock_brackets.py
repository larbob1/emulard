# SPDX-License-Identifier: GPL-3.0-or-later
import json
import unittest

from clock_brackets import anchor_bounds, relation, review_anchors


class ClockBracketTests(unittest.TestCase):
    def review(self, first, last, width=10, drift=10):
        return review_anchors(first, last, max_bracket_ns=width,
                              max_offset_change_ns=drift)

    def test_disjoint_touch_and_overlap(self):
        self.assertEqual(relation((1, 2), (3, 4)), "before")
        self.assertEqual(relation((3, 4), (1, 2)), "after")
        self.assertEqual(relation((1, 2), (2, 4)), "overlap_or_touch")
        self.assertEqual(relation((1, 4), (2, 3)), "overlap_or_touch")
        self.assertEqual(relation((2, 2), (2, 2)), "overlap_or_touch")

    def test_endpoint_bounds_not_midpoint(self):
        self.assertEqual(anchor_bounds(100, 1102, 104), (998, 1002))
        result = self.review((100, 1102, 104), (200, 1202, 204))
        self.assertEqual(result["endpoint_offset_change_bounds_ns"], [-4, 4])
        self.assertEqual(result["status"], "endpoint_change_within_limit")
        self.assertFalse(result["intervening_clock_stability_verified"])

    def test_thresholds_fail_closed(self):
        a = (100, 1102, 104)
        b = (200, 1202, 204)
        self.assertEqual(self.review(a, b, drift=3)["status"],
                         "endpoint_change_uncertain")
        self.assertEqual(self.review(a, b, width=3)["status"],
                         "bracket_too_wide")
        self.assertEqual(self.review(a, (200, 1222, 204))["status"],
                         "endpoint_change_exceeds_limit")
        self.assertEqual(self.review(a, (200, 1182, 204))["status"],
                         "endpoint_change_exceeds_limit")

    def test_bad_timestamps_and_anchor_order(self):
        for a, b in [((1, 0), (2, 3)), ((True, 2), (3, 4)),
                     ((-1, 2), (3, 4)), ((1, 2**64), (3, 4))]:
            with self.assertRaises(ValueError):
                relation(a, b)
        for b in [(104, 1105, 106), (90, 1091, 92)]:
            with self.assertRaises(ValueError):
                self.review((100, 1102, 104), b)
        with self.assertRaises(ValueError):
            self.review((100, 1102, 104), (200, 1202, 204), width=-1)

    def test_absolute_clock_values_not_exported(self):
        offset = 1700000000000000000
        result = self.review((100, offset + 102, 104),
                             (200, offset + 202, 204))
        self.assertNotIn(str(offset), json.dumps(result))
        self.assertEqual(result["endpoint_offset_change_bounds_ns"], [-4, 4])


if __name__ == "__main__":
    unittest.main()
