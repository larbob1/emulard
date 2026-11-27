# SPDX-License-Identifier: GPL-3.0-or-later
import tempfile
import unittest
from pathlib import Path
from apply_cpu_trace_candidate import apply
from propose_cpu_trace_hooks import SOURCE_PATHS, REPLACEMENTS

class CpuTraceApplyTests(unittest.TestCase):
    def fixture(self, root):
        files = {}
        for name, old, _ in REPLACEMENTS:
            files[name] = files.get(name, "") + "\n" + old + "\n"
        for name, text in files.items():
            path = root / SOURCE_PATHS[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return files

    def test_applies_all_hooks_and_refuses_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            apply(root)
            for name, _, new in REPLACEMENTS:
                self.assertIn(new, (root / SOURCE_PATHS[name]).read_text())
            module = (root / SOURCE_PATHS["cpu_trace.rs"]).read_text()
            self.assertIn("struct Controller", module)
            self.assertIn("pub fn initialize", module)
            with self.assertRaises(ValueError):
                apply(root)

    def test_invalid_anchor_leaves_all_files_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            files = self.fixture(root)
            name, old, _ = REPLACEMENTS[-1]
            files[name] = files[name].replace(old, "", 1)
            (root / SOURCE_PATHS[name]).write_text(files[name])
            with self.assertRaises(ValueError):
                apply(root)
            for key, text in files.items():
                self.assertEqual((root / SOURCE_PATHS[key]).read_text(), text)
            self.assertFalse((root / SOURCE_PATHS["cpu_trace.rs"]).exists())

if __name__ == "__main__":
    unittest.main()
