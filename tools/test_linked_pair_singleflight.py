# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile actual linked-pair single-flight helper and native fixtures."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES


class LinkedPairSingleflightTests(unittest.TestCase):
    def block(self):
        new, = [new for old, new in PATCHES["crates/victory-gpu/src/pipeline/host.rs"]
                if old.startswith("    if let Some(pair) = PAIRS.lock()")]
        return new

    def test_runtime_wiring(self):
        block = self.block()
        self.assertIn('std::env::var("VICTORY_MESH_LINK_SINGLEFLIGHT")', block)
        self.assertIn("return linked_once(FLIGHTS.get_or_init(Default::default), key, compile);", block)
        self.assertIn("let pair = compile();", block)
        self.assertIn(".insert(key, pair.clone());", block)
        self.assertEqual(block.count("victory_shader::emit::link_mesh("), 1)

    @unittest.skipUnless(shutil.which("rustc"), "rustc required for portable linked-pair tests")
    def test_actual_helper(self):
        helper = self.block().split("// Single-flight per linked pair.", 1)[1]
        helper = "// Single-flight per linked pair." + helper
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "linked.rs"
            binary = root / "linked-tests.exe"
            source.write_text("use std::sync::Arc;\n" + helper, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary), "linked_pair_singleflight_tests"],
                                    check=True, capture_output=True, text=True, timeout=30)
            self.assertIn("5 passed; 0 failed", result.stdout)
