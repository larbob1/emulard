# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the actual paired-retry policy and its native test fixtures."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES


class ThreadedWaveRetryTests(unittest.TestCase):
    def block(self):
        new, = [new for old, new in PATCHES["crates/victory-shader/src/emit/mod.rs"]
                if "let p = ir::thread_edges" in old]
        return new

    def test_threaded_wiring_and_fingerprint_literal(self):
        block = self.block()
        self.assertIn('std::env::var("VICTORY_WAVE_THREADED_PAIRS")', block)
        self.assertIn("native.stage == HwStage::Cs, native.wave64, lower::host_max_wave(), pairs_on()", block)
        self.assertIn("let res = resource::track(&p, &native.layout, native.stage, Some(&st))?", block)
        self.assertIn("|| paired(c, native, &p, &io, &res)", block)
        self.assertIn("if let Ok((shader, Some(32))) = retry()", block)

    @unittest.skipUnless(shutil.which("rustc"), "rustc required")
    def test_actual_retry_policy(self):
        helper = self.block().split("/// Select at most one", 1)[1]
        helper = "/// Select at most one" + helper.split("/// " + chr(96) + "p" + chr(96) + " translated", 1)[0]
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "retry.rs"
            binary = root / "retry-tests.exe"
            source.write_text(helper, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=30)
            self.assertIn("5 passed; 0 failed", result.stdout)
