# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the review-only early-list persistence model."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("rustc"), "rustc required")
class EarlyListPersistenceTests(unittest.TestCase):
    def test_model(self):
        source = Path(__file__).resolve().parents[1] / "probes" / "early_list_persistence.rs"
        with tempfile.TemporaryDirectory() as work:
            binary = Path(work) / "early-list-tests.exe"
            subprocess.run(
                ["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                check=True, capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                [str(binary)], check=True, capture_output=True, text=True, timeout=30,
            )
            self.assertIn("7 passed; 0 failed", result.stdout)
