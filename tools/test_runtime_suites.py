# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from build_runtime import test_result_counts, test_suite

class RuntimeSuiteTests(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(test_result_counts("test result: ok. 3 passed; 0 failed; 2 ignored"), [(3, 0)])
        self.assertEqual(test_result_counts("test result: FAILED. 0 passed; 1 failed;"), [(0, 1)])
        self.assertEqual(test_result_counts("nothing"), [])

    def test_zero_is_not_success(self):
        for output in ("", "test result: ok. 0 passed; 0 failed;"):
            result = subprocess.CompletedProcess([], 0, stdout=output)
            with patch("build_runtime.subprocess.run", return_value=result):
                with self.assertRaises(subprocess.CalledProcessError):
                    test_suite(Path("."), "victory-gpu", "fake")

    def test_nonzero_passes(self):
        result = subprocess.CompletedProcess([], 0, stdout="test result: ok. 1 passed; 0 failed;")
        with patch("build_runtime.subprocess.run", return_value=result) as run:
            test_suite(Path("."), "victory-gpu", "fake", diagnostics=True)
            self.assertIn("--lib", run.call_args.args[0])
            self.assertIn("--features", run.call_args.args[0])

if __name__ == "__main__":
    unittest.main()
