# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the actual staging-size helper and native fixtures."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES


class StagingNearSizeTests(unittest.TestCase):
    def block(self):
        new, = [new for old, new in PATCHES["crates/victory-gpu/src/texture.rs"]
                if old.startswith("fn staging_buffer(host:")]
        return new

    def test_runtime_wiring(self):
        block = self.block()
        self.assertIn("take_staging_spare(&mut all, size, SPARE_MOST.1, staging_near_size())", block)
        self.assertIn("return Some((buffer, data as *mut u8, actual));", block)
        self.assertIn("write_bytes(data as *mut u8, 0, total as usize)", block)
        self.assertIn("host.upload_buffer(size).map(|(buffer, data)| (buffer, data, size))", block)
        self.assertIn("size > SPARE_MOST.1 || !staging_pool()", block)

    @unittest.skipUnless(shutil.which("rustc"), "rustc required for staging-size tests")
    def test_actual_helper(self):
        helper = self.block().split("// An adjacent class", 1)[1]
        helper = "// An adjacent class" + helper
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "staging.rs"
            binary = root / "staging-tests.exe"
            source.write_text(helper, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary), "staging_near_size_tests"],
                                    check=True, capture_output=True, text=True, timeout=30)
            self.assertIn("6 passed; 0 failed", result.stdout)
