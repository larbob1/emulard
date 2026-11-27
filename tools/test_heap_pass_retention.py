# SPDX-License-Identifier: GPL-3.0-or-later
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from propose_heap_pass_retention import EDITS, preview


class HeapPassRetentionTests(unittest.TestCase):
    def sources(self):
        return {name: "\n".join(old for path, old, _ in EDITS if path == name)
                for name in dict.fromkeys(path for path, _, _ in EDITS)}

    def test_preview_exact_and_nonmutating(self):
        sources = self.sources()
        copy = dict(sources)
        result = preview(sources)
        self.assertEqual(sources,copy)
        for path, _, new in EDITS:
            self.assertIn(new,result[path])
        with self.assertRaises(ValueError):
            preview(result)

    def test_drift_or_duplicate_fails_closed(self):
        for path, old, _ in EDITS:
            for replacement in ("",old+"\n"+old):
                sources = self.sources()
                sources[path] = sources[path].replace(old,replacement)
                with self.assertRaises(ValueError):
                    preview(sources)

    @unittest.skipUnless(shutil.which("rustc"), "rustc required")
    def test_model(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            binary = Path(work) / "heap-tests.exe"
            subprocess.run(["rustc","--edition=2021","--test",str(root/"probes/heap_pass_cache.rs"),
                            "-o",str(binary)],check=True,capture_output=True,text=True)
            result = subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=30)
            self.assertIn("4 passed; 0 failed",result.stdout)
