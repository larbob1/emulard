# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the actual build gate with synthetic driver load/store effects."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES

class PipelineBuildGateTests(unittest.TestCase):
    def test_gate_wiring(self):
        new, = [new for old,new in PATCHES["crates/victory-gpu/src/pipeline/library.rs"]
                if old.startswith("    let began =") and "load from cache" in old]
        self.assertLess(new.index("let _build = pipeline_build_gate(name)"), new.index("let loaded ="))
        self.assertIn('call("load from cache (including lock wait)", name)', new)

    @unittest.skipUnless(shutil.which("rustc"), "rustc required")
    def test_actual_build_gate(self):
        helper, = [new for old,new in PATCHES["crates/victory-gpu/src/pipeline/library.rs"]
                   if old.startswith("/// The pipeline named")]
        helper = helper.split("/// The pipeline named", 1)[0]
        with tempfile.TemporaryDirectory() as work:
            source = Path(work) / "gate.rs"
            binary = Path(work) / "gate-tests.exe"
            source.write_text("use std::sync::{Mutex, MutexGuard, OnceLock};\n" + helper, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=30)
            self.assertIn("5 passed; 0 failed", result.stdout)
