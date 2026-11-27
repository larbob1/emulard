# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from propose_cpu_trace_hooks import preview, REPLACEMENTS


class CpuTraceHookTests(unittest.TestCase):
    def test_exact_replacements_and_refusal(self):
        files = {}
        for name, old, _ in REPLACEMENTS:
            files[name] = files.get(name, "") + old + "\n\n"
        result = preview(files, "model", "bridge")
        for name, old, new in REPLACEMENTS:
            self.assertIn(new, result[name])
            self.assertIn(old, files[name])
        self.assertEqual(result["cpu_trace.rs"], "model\n\nbridge")
        for name, old, _ in REPLACEMENTS:
            bad = dict(files)
            bad[name] = bad[name].replace(old, "")
            with self.assertRaises(ValueError):
                preview(bad, "", "")
            bad[name] = files[name] + old
            with self.assertRaises(ValueError):
                preview(bad, "", "")
        with self.assertRaises(ValueError):
            preview(dict(files, **{"cpu_trace.rs": ""}), "", "")

    @unittest.skipUnless(shutil.which("rustc"), "rustc unavailable")
    def test_compile_review_module(self):
        probes = Path(__file__).resolve().parents[1] / "probes"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cpu_trace.rs"
            source.write_text((probes / "cpu_trace_buffer.rs").read_text() + "\n" +
                              (probes / "cpu_trace_runtime_bridge.rs").read_text())
            binary = Path(directory) / "trace-tests.exe"
            result = subprocess.run(["rustc", "--edition=2021", "--test", str(source),
                                     "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary), "bridge_tests::"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout, r"test result: ok\. 3 passed; 0 failed;")

if __name__ == "__main__":
    unittest.main()
