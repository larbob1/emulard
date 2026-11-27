# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-process publication counterexamples with synthetic bytes only.

Each stage/publish is a separate child process; the parent fixes the order.
This exercises the actual current rename helper, not a D3D12 library or
Windows file mapping. Passing reproduces the hazard, not a production fix.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from apply_pipeline_perf import PATCHES


@unittest.skipUnless(shutil.which("rustc"), "rustc required")
class PipelineCacheProcessOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.build.cleanup)
        root = Path(cls.build.name)
        source = root / "publish.rs"
        cls.binary = root / "publish.exe"
        helper, = [
            new for old, new in PATCHES["crates/victory-gpu/src/pipeline/library.rs"]
            if old.startswith("fn replace_library(")
        ]
        source.write_text(
            'const LIBRARY_FILE: &str = "host-pipelines.bin";\n'
            'const NEXT_FILE: &str = "host-pipelines.next";\n'
            + helper
            + '''
fn main() -> std::io::Result<()> {
    let args: Vec<_> = std::env::args_os().collect();
    assert!(args.len() == 4 || args.len() == 5);
    let action = args[1].to_str().unwrap();
    let dir = std::path::Path::new(&args[2]);
    let tmp = dir.join(&args[3]);
    match action {
        "stage" => std::fs::write(&tmp, args[4].to_str().unwrap().as_bytes()),
        "publish" => replace_library(dir, &tmp),
        _ => panic!("unexpected fixture action"),
    }
}
''', encoding="utf-8")
        subprocess.run(
            ["rustc", "--edition=2021", str(source), "-o", str(cls.binary)],
            check=True, capture_output=True, text=True, timeout=30,
        )

    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.dir = Path(work.name)

    def child(self, action, name, *args, success=True):
        result = subprocess.run(
            [str(self.binary), action, str(self.dir), name, *args],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)

    def stage(self, name, content):
        self.child("stage", name, content)

    def publish(self, name, success=True):
        self.child("publish", name, success=success)

    def test_shared_temp_name_allows_wrong_writer_to_publish(self):
        # Both independent saves derive host-pipelines.tmp from the same
        # published filename. B finishes writing before A's rename.
        tmp = "host-pipelines.tmp"
        self.stage(tmp, "writer-A")
        self.stage(tmp, "writer-B")
        self.publish(tmp)
        self.assertEqual((self.dir / "host-pipelines.bin").read_bytes(), b"writer-B")
        self.publish(tmp, success=False)
        self.assertFalse((self.dir / tmp).exists())

    def test_distinct_temp_names_do_not_merge_stale_snapshots(self):
        # Both writers opened the same baseline before either published.
        # Distinct staging files avoid aliasing but not last-writer wins.
        self.stage("host-pipelines.bin", "baseline")
        self.stage("a.tmp", "baseline+A")
        self.stage("b.tmp", "baseline+B")
        self.publish("a.tmp")
        self.assertEqual((self.dir / "host-pipelines.bin").read_bytes(), b"baseline+A")
        self.publish("b.tmp")
        self.assertEqual((self.dir / "host-pipelines.bin").read_bytes(), b"baseline+B")

    def test_pending_slot_also_has_last_writer_wins_semantics(self):
        self.stage("host-pipelines.bin", "baseline")
        self.stage("host-pipelines.next", "older-pending")
        self.stage("a.tmp", "baseline+A")
        self.stage("b.tmp", "baseline+B")
        self.publish("a.tmp")
        self.assertEqual((self.dir / "host-pipelines.next").read_bytes(), b"baseline+A")
        self.publish("b.tmp")
        self.assertEqual((self.dir / "host-pipelines.next").read_bytes(), b"baseline+B")
        self.assertEqual((self.dir / "host-pipelines.bin").read_bytes(), b"baseline")
