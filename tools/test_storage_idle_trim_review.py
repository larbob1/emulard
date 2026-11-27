# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the standalone worker idle-trim predicate review."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StorageIdleTrimReviewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "standalone Rust compiler unavailable")
    def test_controlled_mutex_condvar_trim(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "storage-idle-trim-tests"
            compile_result = subprocess.run(
                ["rustc", "--edition=2021", "--test",
                 str(ROOT / "probes" / "storage_idle_trim_review.rs"), "-o", str(binary)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(compile_result.returncode, 0,
                             compile_result.stdout + compile_result.stderr)
            for repeat in range(10):
                result = subprocess.run([str(binary), "--test-threads=1"],
                                        capture_output=True, text=True, timeout=40)
                self.assertEqual(result.returncode, 0,
                                 f"repeat={repeat}\n{result.stdout}\n{result.stderr}")
                self.assertRegex(result.stdout, r"test result: ok\. 6 passed; 0 failed; 0 ignored;")
            print("Storage idle trim review: 6 passed x 10 repetitions; 0 failed; 0 ignored",
                  flush=True)


if __name__ == "__main__":
    unittest.main()
