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
                ["rustc", "--edition=2021", "--test", "-C", "opt-level=0",
                 str(ROOT / "probes" / "storage_scratch_review.rs"), "-o", str(binary)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(binary), "--test-threads=1", "--nocapture"],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout, r"test result: ok\. 9 passed; 0 failed; 0 ignored;")
            rows = [line for line in result.stdout.splitlines()
                    if "Storage scratch allocator calls:" in line]
            self.assertEqual(len(rows), 1, result.stdout)
            row = rows[0][rows[0].index("Storage scratch allocator calls:"):]
            self.assertRegex(row, r"baseline_acquisitions=100 .*reuse_acquisitions=1 ")
            print(row, flush=True)
            mixed = [line[line.index("Storage scratch mixed calls:"):]
                     for line in result.stdout.splitlines()
                     if "Storage scratch mixed calls:" in line]
            modes = (("disabled", 0), ("bounded", 65536), ("cap4k", 4096),
                     ("cap8k", 8192), ("cap16k", 16384), ("cap32k", 32768),
                     ("cap128k", 131072))
            self.assertEqual(len(mixed), len(modes), result.stdout)
            for (mode, cap), line in zip(modes, mixed):
                fields = dict(field.split("=", 1) for field in
                              line.removeprefix("Storage scratch mixed calls: ").split())
                self.assertEqual(fields["mode"], mode)
                self.assertEqual(int(fields["cap"]), cap)
                self.assertEqual(int(fields["requests"]), 128)
                self.assertEqual(int(fields["failed"]), 16)
                self.assertEqual(int(fields["nonzero"]), 120)
                self.assertEqual(int(fields["input_bytes"]), 2458368)
                self.assertEqual(int(fields["baseline_acquisitions"]), 120)
                self.assertEqual(int(fields["baseline_requested"]), 2458368)
                self.assertEqual(int(fields["trim_events"]), 9)
                self.assertEqual(int(fields["final_idle"]), 0)
                self.assertLessEqual(int(fields["peak_idle"]), cap)
                self.assertEqual(int(fields["reuse_acquisitions"]),
                                 int(fields["reuse_realloc"]) + int(fields["reuse_dealloc"]))
                print(line, flush=True)
            print("Storage scratch Vec review: 9 passed; 0 failed; 0 ignored", flush=True)


if __name__ == "__main__":
    unittest.main()
