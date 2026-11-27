# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for frozen metadata matching, not external verification."""
import copy
import unittest

from ai0_review_queue import EXPECTED, verify


class ReviewQueueTests(unittest.TestCase):
    def test_frozen_metadata(self):
        r = verify(copy.deepcopy(EXPECTED))
        self.assertEqual((r["matched_proposals"], r["distinct_repository_paths"],
                          r["added_lines"]), (11, 24, 2182))
        self.assertEqual(r["shared_upstream_groups"],
                         {"texture": [64, 65], "draw": [67, 69, 70], "memory": [71, 72]})
        self.assertEqual(r["independent_review"], "REQUIRED")
        self.assertEqual(r["performance_evidence"], "NOT_ESTABLISHED")

    def test_order_is_irrelevant(self):
        rows = copy.deepcopy(EXPECTED)
        rows.reverse()
        for row in rows:
            row["files"].reverse()
        self.assertEqual(verify(rows), verify(EXPECTED))

    def test_reject_incomplete_duplicate_extra(self):
        for rows in ([], EXPECTED[:-1], EXPECTED[:-1] + [EXPECTED[0]],
                     EXPECTED + [EXPECTED[0]], {}, None):
            with self.assertRaises(ValueError):
                verify(rows)

    def test_reject_identity_status_and_count_drift(self):
        for key, value in (("head", "bad"), ("base", "bad"), ("draft", False),
                           ("state", "closed"), ("ahead", True), ("behind", 1),
                           ("synthetic_job", 0), ("synthetic_head", "bad"),
                           ("synthetic_status", "failure"), ("portable_status", "success"),
                           ("python_passed", 0), ("range_passed", 0),
                           ("group", "other"), ("run", 0)):
            rows = copy.deepcopy(EXPECTED)
            rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify(rows)

    def test_reject_path_change_or_extra_field(self):
        rows = copy.deepcopy(EXPECTED)
        rows[0]["files"][0][0] = rows[1]["files"][0][0]
        with self.assertRaises(ValueError):
            verify(rows)
        rows = copy.deepcopy(EXPECTED)
        rows[0]["approved"] = True
        with self.assertRaises(ValueError):
            verify(rows)

    def test_reject_malformed_file_rows(self):
        for files in (None, [], ["bad"], [[1, "added", 1, 0]],
                      [["path", "added", 1]], [["path", "added", 1, 0, 5]]):
            rows = copy.deepcopy(EXPECTED)
            rows[0]["files"] = files
            with self.subTest(files=files), self.assertRaises(ValueError):
                verify(rows)


if __name__ == "__main__":
    unittest.main()
