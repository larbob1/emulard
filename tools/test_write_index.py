# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_memory_patch import WRITE_INDEX_EDITS, patch_write_index

class WriteIndexPatcherTests(unittest.TestCase):
    def test_source_edits(self):
        data = "\n".join(a for a, _ in WRITE_INDEX_EDITS).encode()
        result = patch_write_index(data).decode()
        for _, after in WRITE_INDEX_EDITS:
            self.assertIn(after, result)

    def test_missing_anchor(self):
        with self.assertRaises(ValueError):
            patch_write_index(b"unknown")

    def test_duplicate_anchor(self):
        data = "\n".join(a for a, _ in WRITE_INDEX_EDITS)
        with self.assertRaises(ValueError):
            patch_write_index((data + "\n" + WRITE_INDEX_EDITS[0][0]).encode())

    def test_crlf(self):
        data = "\r\n".join(a for a, _ in WRITE_INDEX_EDITS).encode()
        result = patch_write_index(data)
        self.assertEqual(result.count(b"\n"), result.count(b"\r\n"))

if __name__ == "__main__":
    unittest.main()
