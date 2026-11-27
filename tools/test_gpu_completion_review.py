# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the isolated GPU completion evidence model, not the runtime."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("rustc"), "rustc required")
class GPUCompletionReviewTests(unittest.TestCase):
    def test_completion_evidence_and_ordered_publication(self):
        source = Path(__file__).resolve().parents[1] / "probes" / "gpu_completion_review.rs"
        with tempfile.TemporaryDirectory() as work:
            exe = Path(work) / "gpu-completion-review.exe"
            subprocess.run(
                ["rustc", "--edition=2021", "--test", str(source), "-o", str(exe)],
                check=True, capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                [str(exe)], check=True, capture_output=True, text=True, timeout=10,
            )
            self.assertIn("6 passed; 0 failed", result.stdout)
            print("GPU completion review Rust proof: 6 passed; 0 failed")
