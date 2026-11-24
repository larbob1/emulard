# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from unittest.mock import patch
import apply_memory_patch as candidate

class PatcherTests(unittest.TestCase):
    def test_blob_hash(self):
        self.assertEqual(candidate.blob_hash(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_unreviewed_revision(self):
        with self.assertRaises(ValueError):
            candidate.patch_source(candidate.HOST, b"unexpected")

    def test_host_edit(self):
        lines = [f"line{i}\n" for i in range(1, 6500)]
        lines[4867:4869] = ["                *n += len;\n", "                return;\n"]
        src = "".join(lines).encode()
        with patch.dict(candidate.EXPECTED, {candidate.HOST: candidate.blob_hash(src)}):
            result = candidate.patch_source(candidate.HOST, src).decode()
        self.assertIn("line1592\n    raw_copy_progress:", result)
        self.assertIn("line1604\n#[derive(Default)]", result)
        self.assertIn("line5053\n    /// Track", result)
        self.assertIn("*n += len;\n                deferred.refreshed.clear();\n                deferred.raw_copy_progress.invalidate_reads();\n                return;", result)

    def test_memory_edit_and_crlf(self):
        src = "".join(f"line{i}\n" for i in range(1, 321)).encode()
        with patch.dict(candidate.EXPECTED, {candidate.MEMORY: candidate.blob_hash(src)}):
            result = candidate.patch_source(candidate.MEMORY, src.replace(b"\n", b"\r\n")).decode()
        self.assertIn("line259\r\nline261\r\n", result)
        self.assertIn("line292\r\n    let (read_from", result)
        self.assertNotIn("line309\r\n", result)

if __name__ == "__main__":
    unittest.main()
