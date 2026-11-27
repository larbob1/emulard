# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import tempfile
import unittest
from build_runtime import apply_patch

class PatchLineEndingTests(unittest.TestCase):
    def test_crlf_patch_against_lf_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            source = root / "sample.txt"
            source.write_bytes(b"one\ntwo\nthree\n")
            patch = root / "sample.patch"
            patch.write_bytes(b"--- a/sample.txt\r\n+++ b/sample.txt\r\n@@ -1,3 +1,3 @@\r\n one\r\n-two\r\n+TWO\r\n three\r\n")
            apply_patch(patch, root)
            self.assertEqual(source.read_bytes(), b"one\nTWO\nthree\n")
            with self.assertRaises(subprocess.CalledProcessError):
                apply_patch(patch, root)
            self.assertEqual(source.read_bytes(), b"one\nTWO\nthree\n")

if __name__ == "__main__":
    unittest.main()
