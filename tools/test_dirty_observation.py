# SPDX-License-Identifier: GPL-3.0-or-later
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from propose_dirty_observation import EDITS, preview, ROOT


class ObservationProposalTests(unittest.TestCase):
    def test_exact_preview_does_not_mutate_inputs(self):
        sources = {name: "\n".join(old for path, old, _ in EDITS if path == name)
                   for name in dict.fromkeys(path for path, _, _ in EDITS)}
        original = dict(sources)
        result = preview(sources, "mod dirty_observation {}")
        self.assertEqual(sources, original)
        for name, _, new in EDITS:
            self.assertIn(new, result[name])
        self.assertIn("mod dirty_observation {}", result["crates/victory-gpu/src/shadow.rs"])
        with self.assertRaises(ValueError):
            preview(result, "")

    def test_missing_and_duplicate_anchors_rejected(self):
        for name, old, _ in EDITS:
            for replacement in ("", old + "\n" + old):
                sources = {n: "\n".join(a for path, a, _ in EDITS if path == n)
                           for n in dict.fromkeys(path for path, _, _ in EDITS)}
                sources[name] = sources[name].replace(old, replacement)
                with self.assertRaises(ValueError):
                    preview(sources, "")

    @unittest.skipUnless(shutil.which("rustc"), "rustc required")
    def test_compile_exact_review_helper(self):
        with tempfile.TemporaryDirectory() as work:
            source = Path(work) / "bridge.rs"
            source.write_text("mod shadow {\n" +
                              (ROOT / "probes/dirty_observation_bridge.rs").read_text() + "\n}", encoding="utf-8")
            binary = Path(work) / "tests.exe"
            subprocess.run(["rustc", "--edition=2021", "--test", "--cfg", 'feature="diagnostics"',
                            str(source), "-o", str(binary)], check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=30)
            self.assertIn("6 passed; 0 failed", result.stdout)
