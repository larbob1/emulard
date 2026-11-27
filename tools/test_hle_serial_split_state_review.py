"""Compile the isolated split worker-state ownership review."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class HleSerialSplitStateReview(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "standalone Rust compiler unavailable")
    def test_serial_split_state_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / "hle-serial-split-state"
            result = subprocess.run(
                ["rustc", "--edition=2021", "--test",
                 str(ROOT / "probes" / "hle_serial_split_state_review.rs"), "-o", str(binary)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for _ in range(10):
                result = subprocess.run([str(binary), "--test-threads=1"],
                                        capture_output=True, text=True, timeout=40)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("test result: ok. 10 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
                              result.stdout)
            print("HLE serial split state review: 10 runs, each 10 passed; 0 failed; 0 ignored", flush=True)


if __name__ == "__main__":
    unittest.main()
