# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the isolated retirement ordering model, not the runtime."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("rustc"), "rustc required")
class RetirementPublicationTests(unittest.TestCase):
    def test_threaded_retirement_model(self):
        source = Path(__file__).resolve().parents[1] / "probes" / "retirement_publication_review.rs"
        with tempfile.TemporaryDirectory() as work:
            exe = Path(work) / "retirement-review.exe"
            subprocess.run(
                ["rustc", "--edition=2021", "--test", str(source), "-o", str(exe)],
                check=True, capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                [str(exe)], check=True, capture_output=True, text=True, timeout=30,
            )
            self.assertIn("5 passed; 0 failed", result.stdout)
