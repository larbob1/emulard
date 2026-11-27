"""Compile standalone event-driven serialized ownership review."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class HleSerialEventReview(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "standalone Rust compiler unavailable")
    def test_serial_event_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / "hle-serial-event"
            result = subprocess.run(
                ["rustc", "--edition=2021", "--test",
                 str(ROOT / "probes" / "hle_serial_event_review.rs"), "-o", str(binary)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for _ in range(10):
                result = subprocess.run([str(binary), "--test-threads=1"],
                                        capture_output=True, text=True, timeout=40)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
                              result.stdout)
            print("HLE serial event review: 10 runs, each 6 passed; 0 failed; 0 ignored", flush=True)


if __name__ == "__main__":
    unittest.main()
