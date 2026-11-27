# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from dirty_policy import PAGE, Submission, merge_bytes

class DirtyPolicyTests(unittest.TestCase):
    def test_per_submission_and_fence(self):
        a, b = Submission(1), Submission(2)
        a.mark(PAGE, 4)
        b.mark(2 * PAGE, 4)
        with self.assertRaises(ValueError):
            a.ranges([(0, 3 * PAGE, True, False)])
        with self.assertRaises(ValueError):
            a.finish(2)
        a.finish(1)
        self.assertEqual(a.ranges([(0, 3 * PAGE, True, False)]), ([(PAGE, 2 * PAGE)], []))
        b.finish(2)
        self.assertEqual(b.ranges([(0, 3 * PAGE, True, False)]), ([(2 * PAGE, 3 * PAGE)], []))

    def test_cross_page_and_partial_range(self):
        a = Submission(1)
        a.mark(PAGE - 2, 4)
        a.finish(1)
        self.assertEqual(a.ranges([(PAGE - 8, PAGE + 8, True, False)]),
                         ([(PAGE - 8, PAGE), (PAGE, PAGE + 8)], []))

    def test_withhold_only_known_dependent_instrumented_ranges(self):
        a = Submission(1)
        a.mark(PAGE, 4)
        a.mark(3 * PAGE, 4, mapped=False)
        a.finish(1)
        self.assertEqual(a.ranges([(PAGE, 2 * PAGE, True, False),
                                   (PAGE, 2 * PAGE, True, True),
                                   (0, PAGE, False, False)]),
                         ([(PAGE, 2 * PAGE), (0, PAGE)], [(PAGE, 2 * PAGE)]))

    def test_cpu_changes_preserved(self):
        self.assertEqual(merge_bytes(b"abcd", b"aXcd", b"abcY"), b"aXcY")

    def test_only_dirty_pages_in_model(self):
        a = Submission(1)
        a.mark(7 * PAGE, 4)
        a.mark(89 * PAGE, 4)
        a.finish(1)
        ranges, withheld = a.ranges([(0, 100 * PAGE, True, False)])
        self.assertEqual(sum(hi-lo for lo,hi in ranges), 2 * PAGE)
        self.assertEqual(withheld, [])

    def test_unknown_tracking_falls_back(self):
        a = Submission(1)
        a.finish(1)
        self.assertEqual(a.ranges([(0, PAGE, False, False)]), ([(0, PAGE)], []))

if __name__ == "__main__":
    unittest.main()
