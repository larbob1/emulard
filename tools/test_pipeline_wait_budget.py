# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the runtime's actual pipeline wait accounting and native regression fixtures."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES


@unittest.skipUnless(shutil.which("rustc"), "rustc required for portable wait-budget tests")
class PipelineWaitBudgetTests(unittest.TestCase):
    def test_actual_wait_accounting(self):
        block, = [new for old, new in PATCHES["crates/victory-gpu/src/pipeline/make.rs"]
                  if old.startswith("/// Waits for ") and "fn wait(" in old]
        helpers = block.split("/// Waits for ", 1)[0]
        self.assertIn("reserve_wait(&mut spent, frame.max(crate::frame::current()), budget, shared)", block)
        self.assertIn("settle_wait(&mut spent, charged_frame, left, waited, shared)", block)
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "wait_budget.rs"
            binary = root / "wait-budget-tests.exe"
            source.write_text("use std::time::Duration;\n" + helpers, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary), "wait_budget_order_tests"], check=True,
                                    capture_output=True, text=True)
            self.assertIn("5 passed; 0 failed", result.stdout)
