# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_heap_patch import SPECS, transform

class HeapPatchTests(unittest.TestCase):
    def test_source_edits(self):
        for _, _, edits in SPECS:
            source = "\n".join(a for a, _ in edits)
            result = transform(source.encode(), edits).decode()
            for before, after in edits:
                if after:
                    self.assertIn(after, result)
                else:
                    self.assertNotIn(before, result)

    def test_unknown_revision_anchor(self):
        with self.assertRaises(ValueError):
            transform(b"unknown", SPECS[0][2])

    def test_duplicate_anchor(self):
        for _, _, edits in SPECS:
            for before, after in edits:
                with self.assertRaises(ValueError):
                    transform((before + before).encode(), [(before, after)])

    def test_crlf_preservation(self):
        for _, _, edits in SPECS:
            source = "\n".join(a for a, _ in edits).replace("\n", "\r\n")
            result = transform(source.encode(), edits)
            self.assertEqual(result.count(b"\n"), result.count(b"\r\n"))

if __name__ == "__main__":
    unittest.main()
