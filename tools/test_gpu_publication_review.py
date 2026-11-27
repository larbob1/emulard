# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile and run the review-only GPU publication evidence ledger."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("rustc"), "rustc required")
class GPUPublicationReviewTests(unittest.TestCase):
    def test_domain_and_partial_publication(self):
        source = Path(__file__).resolve().parents[1] / "probes" / "gpu_publication_review.rs"
        with tempfile.TemporaryDirectory() as work:
            exe = Path(work) / "gpu-publication-review.exe"
            subprocess.run(
                ["rustc", "--edition=2021", "--test", str(source), "-o", str(exe)],
                check=True, capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                [str(exe)], check=True, capture_output=True, text=True, timeout=10,
            )
            self.assertIn("14 passed; 0 failed; 0 ignored", result.stdout)
            print("GPU publication review Rust proof: 14 passed; 0 failed; 0 ignored")
