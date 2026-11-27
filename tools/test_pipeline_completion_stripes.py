# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile actual completion routing, notification and predicate wait helpers."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES


class PipelineCompletionStripeTests(unittest.TestCase):
    def test_wiring(self):
        pairs = PATCHES["crates/victory-gpu/src/pipeline/make.rs"]
        self.assertTrue(any("notify_completion(completion(self));" in new for _,new in pairs))
        self.assertTrue(any("wait_completion(completion(p), started, left, || p.made.get().is_some())" in new
                            for _,new in pairs))

    @unittest.skipUnless(shutil.which("rustc"), "rustc required")
    def test_actual_helpers(self):
        new, = [new for old,new in PATCHES["crates/victory-gpu/src/pipeline/make.rs"]
                if old.startswith("/// Signalled whenever")]
        with tempfile.TemporaryDirectory() as work:
            source = Path(work) / "completion.rs"
            binary = Path(work) / "completion-tests.exe"
            source.write_text("use std::sync::{Mutex, Condvar, OnceLock};\n"
                              "use std::sync::atomic::{AtomicBool, Ordering};\n"
                              "use std::time::{Instant, Duration};\nstruct Pending;\n"+new,encoding="utf-8")
            subprocess.run(["rustc","--edition=2021","--test",str(source),"-o",str(binary)],
                           check=True,capture_output=True,text=True)
            result = subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=30)
            self.assertIn("5 passed; 0 failed",result.stdout)
