# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the standalone storage scratch review using existing unittest discovery."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StorageScratchReviewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "standalone Rust compiler unavailable")
    def test_actual_vec_reuse_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "storage-scratch-tests"
            compiled = subprocess.run(
                ["rustc", "--edition=2021", "--test",
                 str(ROOT / "probes" / "storage_scratch_review.rs"), "-o", str(binary)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(binary), "--test-threads=1"],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout, r"test result: ok\. 7 passed; 0 failed; 0 ignored;")
            print("Storage scratch Vec review: 7 passed; 0 failed; 0 ignored", flush=True)


if __name__ == "__main__":
    unittest.main()
