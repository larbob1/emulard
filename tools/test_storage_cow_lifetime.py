# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the isolated Cow scope proof using the existing synthetic test job."""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class StorageCowLifetimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "standalone Rust compiler unavailable")
    def test_actual_rust_cow_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / "storage-cow-tests"
            compiled = subprocess.run(
                ["rustc", "--edition=2021", "--test",
                 str(ROOT / "probes" / "storage_cow_lifetime.rs"), "-o", str(binary)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(binary), "--test-threads=1"],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout, re.compile(r"test result: ok\. 7 passed; 0 failed; 0 ignored;"))
            print("Storage Cow lifetime Rust proof: 7 passed; 0 failed; 0 ignored", flush=True)


if __name__ == "__main__":
    unittest.main()
