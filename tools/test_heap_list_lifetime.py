# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile conservative descriptor owner/list/flight lifetime fixture."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class HeapListLifetimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "rustc required")
    def test_model(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            binary = Path(work) / "heap-list-tests.exe"
            subprocess.run(["rustc", "--edition=2021", "--test",
                            str(root / "probes/heap_list_lifetime.rs"), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True,
                                    text=True, timeout=30)
            self.assertIn("8 passed; 0 failed", result.stdout)
