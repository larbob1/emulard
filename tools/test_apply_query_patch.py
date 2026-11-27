# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from unittest.mock import patch

import apply_query_patch as candidate
from apply_memory_patch import blob_hash

class QueryPatcherTests(unittest.TestCase):
    def fixture(self):
        return (candidate.ANCHOR + "\n" + candidate.BEFORE + "\n").encode()

    def test_revision_guard(self):
        with self.assertRaises(ValueError):
            candidate.patch_source(self.fixture())

    def test_exact_edit(self):
        data = self.fixture()
        with patch.object(candidate, "EXPECTED", blob_hash(data)):
            result = candidate.patch_source(data).decode()
        self.assertIn(candidate.HELPER + candidate.ANCHOR, result)
        self.assertIn(candidate.AFTER, result)
        self.assertNotIn(candidate.BEFORE, result)

    def test_missing_anchor_rejected_even_with_matching_hash(self):
        data = candidate.BEFORE.encode()
        with patch.object(candidate, "EXPECTED", blob_hash(data)):
            with self.assertRaises(ValueError):
                candidate.patch_source(data)

    def test_crlf_preserved(self):
        data = self.fixture()
        with patch.object(candidate, "EXPECTED", blob_hash(data)):
            result = candidate.patch_source(data.replace(b"\n", b"\r\n"))
        self.assertEqual(result.count(b"\n"), result.count(b"\r\n"))

if __name__ == "__main__":
    unittest.main()
