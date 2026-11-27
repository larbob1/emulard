# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the standalone actual trace model; no runtime build or CI edit."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


class CpuTraceBufferTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "rustc unavailable")
    def test_portable_buffer(self):
        source = Path(__file__).resolve().parents[1] / "probes" / "cpu_trace_buffer.rs"
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "trace-tests.exe"
            result = subprocess.run(["rustc", "--edition=2021", "--test", str(source),
                                     "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout, r"test result: ok\. 23 passed; 0 failed;")


if __name__ == "__main__":
    unittest.main()
