# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the isolated readback slot model; no renderer or D3D12 required."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ReadbackSlotTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "rustc required for dirty-flight model")
    def test_model(self):
        source = Path(__file__).resolve().parents[1] / "probes" / "readback_slots.rs"
        with tempfile.TemporaryDirectory() as work:
            binary = Path(work) / "readback-slot-tests.exe"
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True,
                                    text=True, timeout=60)
            self.assertIn("6 passed; 0 failed", result.stdout)
