# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for frozen metadata matching, not external verification."""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
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


class StrictCliTests(unittest.TestCase):
    def run_snapshot(self, raw):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(raw, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(Path(__file__).with_name("ai0_review_queue.py")),
                 str(path)], capture_output=True, text=True, timeout=10)

    def test_valid_historical_scope(self):
        result = self.run_snapshot(json.dumps(EXPECTED))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HISTORICAL_PR_62_TO_72_ONLY", result.stdout)
        self.assertIn("not current inventory", result.stdout)

    def test_duplicate_keys_rejected(self):
        raw = json.dumps(EXPECTED)
        for prefix in ('"pr": 62, ', '"pr": 999, ',
                       r'"\u0070r": 62, '):
            with self.subTest(prefix=prefix):
                result = self.run_snapshot(raw.replace('{"pr": 62,',
                    '{' + prefix + '"pr": 62,', 1))
                self.assertEqual(result.returncode, 1)
                self.assertIn("INVALID", result.stdout)

    def test_nested_duplicate_keys_rejected(self):
        from ai0_review_queue import reject_duplicate_keys
        for raw in ('{"nested":{"x":1,"x":1}}',
                    '{"nested":{"x":1,"x":2}}'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    json.loads(raw, object_pairs_hook=reject_duplicate_keys)
                result = self.run_snapshot(raw)
                self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
