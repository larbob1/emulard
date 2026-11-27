# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile exact init observation helper with synthetic HRESULTs."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES

class LibraryInitDiagnosticTests(unittest.TestCase):
    def test_exact_wiring(self):
        pairs = PATCHES["crates/victory-gpu/src/pipeline/library.rs"]
        _, device = next((old,new) for old,new in pairs if "device.cast::<ID3D12Device1>()" in old)
        _, make = next((old,new) for old,new in pairs if "device.CreatePipelineLibrary" in old)
        self.assertIn("cast::<ID3D12Device1>(), 0).ok()?",device)
        self.assertIn("if !bytes.is_empty()",make)
        self.assertIn("return device.CreatePipelineLibrary::<ID3D12PipelineLibrary>(bytes)?.cast();",make)
        self.assertIn("CreatePipelineLibrary::<ID3D12PipelineLibrary>(bytes), 1)?",make)
        self.assertIn("library_init_result(base.cast(), 2)",make)

    @unittest.skipUnless(shutil.which("rustc"), "rustc required")
    def test_actual_observer(self):
        new, = [new for old,new in PATCHES["crates/victory-gpu/src/pipeline/library.rs"]
                if old == "fn library() -> Option<&'static Library> {"]
        # Compile actual pure functions and their native tests, not the Windows wrapper.
        pure = new.split("fn library_init_result<T>",1)[0]
        tests = new.split("#[cfg(test)]",1)[1].split("fn library() ->",1)[0]
        with tempfile.TemporaryDirectory() as work:
            source = Path(work)/"observe.rs"
            binary = Path(work)/"observe-tests.exe"
            source.write_text(pure+"#[cfg(test)]"+tests,encoding="utf-8")
            subprocess.run(["rustc","--edition=2021","--test",str(source),"-o",str(binary)],
                            check=True,capture_output=True,text=True)
            result = subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=30)
            self.assertIn("4 passed; 0 failed",result.stdout)
