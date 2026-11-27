# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from unittest.mock import patch
import apply_relative_patch as candidate
from apply_memory_patch import blob_hash

class RelativePatchTests(unittest.TestCase):
    def test_anchors(self):
        for before, after in candidate.EDITS:
            source = before.encode()
            with patch.object(candidate, "EXPECTED", blob_hash(source)), patch.object(candidate, "EDITS", [(before, after)]):
                self.assertEqual(candidate.transform(source).decode(), after)

    def test_unknown_source(self):
        with self.assertRaises(ValueError):
            candidate.transform(b"unexpected")

    def test_duplicate_anchor(self):
        before, after = candidate.EDITS[0]
        source = (before + before).encode()
        with patch.object(candidate, "EXPECTED", blob_hash(source)):
            with self.assertRaises(ValueError):
                candidate.transform(source)

if __name__ == "__main__":
    unittest.main()
