# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_memory_patch import blob_hash
import apply_wave_patch as candidate

class WavePatcherTests(unittest.TestCase):
    def test_each_source_edit(self):
        for path, _, edits in candidate.SPECS:
            with self.subTest(path=path):
                data = "\n".join(a for a, _ in edits).encode()
                result = candidate.patch_source(data, blob_hash(data), edits).decode()
                for _, after in edits:
                    self.assertIn(after, result)

    def test_wrong_revision(self):
        for _, expected, edits in candidate.SPECS:
            with self.assertRaises(ValueError):
                candidate.patch_source(b"unknown", expected, edits)

    def test_missing_anchors(self):
        for _, _, edits in candidate.SPECS:
            with self.assertRaises(ValueError):
                candidate.patch_source(b"", blob_hash(b""), edits)

    def test_duplicate_anchor(self):
        for _, _, edits in candidate.SPECS:
            data = ("\n".join(a for a, _ in edits) + "\n" + edits[0][0]).encode()
            with self.assertRaises(ValueError):
                candidate.patch_source(data, blob_hash(data), edits)

if __name__ == "__main__":
    unittest.main()
