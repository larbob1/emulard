# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the actual prepared queue and native promotion fixtures with minimal stubs."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES

STUBS = r'''
mod pipeline {
    use std::sync::Arc;
    pub struct Shader { pub stage: &'static str }
    pub fn shader(stage: &'static str, _: &[u8]) -> Arc<Shader> { Arc::new(Shader { stage }) }
    mod make {
        use std::collections::VecDeque;
        use std::sync::{Arc, OnceLock};
        use std::sync::atomic::{AtomicU8, Ordering};
        use super::Shader;
        const NOT_QUEUED: u8 = 0;
        const EARLY: u8 = 1;
        const REQUESTED: u8 = 2;
        const MAKING: u8 = 3;
        struct Pending { shaders: Vec<Arc<Shader>>, queue_state: AtomicU8 }
        impl Pending {
            fn new(shaders: Vec<Arc<Shader>>, _: Option<()>) -> Self {
                Self { shaders, queue_state: AtomicU8::new(NOT_QUEUED) }
            }
        }
        fn graphics_burst() -> Option<usize> { None }
'''

@unittest.skipUnless(shutil.which("rustc"), "rustc required for portable queue tests")
class PipelineQueueTests(unittest.TestCase):
    def test_prepared_queue_promotion(self):
        block, = [new for old, new in PATCHES["crates/victory-gpu/src/pipeline/make.rs"]
                  if old.startswith("struct Queue {")]
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "queue.rs"
            binary = root / "queue-tests.exe"
            source.write_text(STUBS + block + "\n}}\n", encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary), "queue_promotion_tests"],
                                    check=True, capture_output=True, text=True, timeout=30)
            self.assertIn("5 passed; 0 failed", result.stdout)
