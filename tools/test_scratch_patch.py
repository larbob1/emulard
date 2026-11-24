# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_memory_patch import SCRATCH_EDITS, patch_scratch

class ScratchPatcherTests(unittest.TestCase):
    def test_exact_edits(self):
        data = "\n".join(a for a, _ in SCRATCH_EDITS).encode()
        result = patch_scratch(data).decode()
        for _, after in SCRATCH_EDITS:
            self.assertIn(after, result)

    def test_missing_anchor(self):
        with self.assertRaises(ValueError):
            patch_scratch(b"unknown")

    def test_duplicate_anchor(self):
        data = "\n".join(a for a, _ in SCRATCH_EDITS) + "\n" + SCRATCH_EDITS[0][0]
        with self.assertRaises(ValueError):
            patch_scratch(data.encode())

    def test_crlf(self):
        data = "\r\n".join(a for a, _ in SCRATCH_EDITS).encode()
        result = patch_scratch(data)
        self.assertEqual(result.count(b"\n"), result.count(b"\r\n"))

if __name__ == "__main__":
    unittest.main()
