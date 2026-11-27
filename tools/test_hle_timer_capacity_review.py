"""Compile standalone timer capacity review using existing test discovery."""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class HleTimerCapacityReview(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "standalone Rust compiler unavailable")
    def test_capacity_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / "hle-timer-capacity"
            result = subprocess.run(
                ["rustc", "--edition=2021", "--test",
                 str(ROOT / "probes" / "hle_timer_capacity_review.rs"), "-o", str(binary)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for _ in range(10):
                result = subprocess.run([str(binary), "--test-threads=1"],
                                        capture_output=True, text=True, timeout=40)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertRegex(result.stdout, re.compile(
                    r"test result: ok\. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"))
            print("HLE timer capacity review: 10 runs, each 5 passed; 0 failed; 0 ignored", flush=True)


if __name__ == "__main__":
    unittest.main()
