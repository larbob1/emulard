# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from build_runtime import validate_paired

class ValidationPlanTests(unittest.TestCase):
    def test_keeps_going_but_fails(self):
        with patch("build_runtime.test_suite") as suite, patch("build_runtime.run") as run:
            suite.side_effect = [subprocess.CalledProcessError(1, ["test"])] + [None] * 40
            with self.assertRaises(subprocess.CalledProcessError):
                validate_paired(Path("."), keep_going=True)
            self.assertGreater(suite.call_count, 10)
            self.assertEqual(run.call_count, 2)

    def test_pipeline_stream_gate(self):
        with patch("build_runtime.test_suite") as suite, patch("build_runtime.run") as run:
            validate_paired(Path("."))
        selected = [c for c in suite.call_args_list if c.args[1:3] == ("victory-gpu", "pipeline_stream_")]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].kwargs["expected"], 9)
        self.assertEqual(run.call_count, 2)

    def test_exact_native_count(self):
        from build_runtime import test_suite
        for output, ok in (
            ("test result: ok. 9 passed; 0 failed; 0 ignored;", True),
            ("test result: ok. 8 passed; 0 failed; 1 ignored;", False),
            ("test result: ok. 10 passed; 0 failed;", False),
            ("test result: ok. 4 passed; 0 failed;\ntest result: ok. 5 passed; 0 failed;", False),
            ("test result: FAILED. 9 passed; 1 failed;", False),
        ):
            with self.subTest(output=output), patch("build_runtime.subprocess.run") as run:
                run.return_value.stdout = output
                if ok:
                    test_suite(Path("."), "victory-gpu", "pipeline_stream_", expected=9)
                else:
                    with self.assertRaises(subprocess.CalledProcessError):
                        test_suite(Path("."), "victory-gpu", "pipeline_stream_", expected=9)

    def test_default_fails_fast(self):
        with patch("build_runtime.test_suite", side_effect=subprocess.CalledProcessError(1, ["test"])) as suite, patch("build_runtime.run") as run:
            with self.assertRaises(subprocess.CalledProcessError):
                validate_paired(Path("."))
            self.assertEqual(suite.call_count, 1)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
