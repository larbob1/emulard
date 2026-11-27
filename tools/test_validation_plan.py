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

    def test_mapping_diagnostic_fresh_modes(self):
        with patch("build_runtime.test_suite") as suite, patch("build_runtime.run") as run:
            validate_paired(Path("."))
        selected = [c for c in suite.call_args_list if c.kwargs.get("ignored")]
        self.assertEqual(len(selected), 2)
        self.assertEqual([c.kwargs["env"]["VICTORY_MAPPING_DIAGNOSTIC"] for c in selected], ["0", "1"])
        for c in selected:
            self.assertEqual(c.args[1:3], ("victory-hle", "mapping_diagnostic_actual_views"))
            self.assertTrue(c.kwargs["diagnostics"])
            self.assertEqual(c.kwargs["expected"], 1)
        self.assertEqual(run.call_count, 2)

    def test_mapping_diagnostic_requires_explicit_mode_and_count(self):
        from build_runtime import test_suite
        for mode in ("0", "1"):
            env = {"VICTORY_MAPPING_DIAGNOSTIC": mode}
            for output, ok in (("test result: ok. 1 passed; 0 failed;", True),
                               ("test result: ok. 0 passed; 0 failed;", False),
                               ("test result: ok. 2 passed; 0 failed;", False),
                               ("test result: ok. 1 passed; 0 failed;\ntest result: ok. 0 passed; 0 failed;", False)):
                with self.subTest(mode=mode, output=output), patch("build_runtime.subprocess.run") as run:
                    run.return_value.stdout = output
                    if ok:
                        test_suite(Path("."), "victory-hle", "mapping_diagnostic_actual_views", env=env, diagnostics=True, expected=1, ignored=True)
                    else:
                        with self.assertRaises(subprocess.CalledProcessError):
                            test_suite(Path("."), "victory-hle", "mapping_diagnostic_actual_views", env=env, diagnostics=True, expected=1, ignored=True)
                    self.assertEqual(run.call_args.args[0], ["cargo", "test", "--locked", "-p", "victory-hle", "--lib",
                        "--features", "diagnostics", "mapping_diagnostic_actual_views", "--", "--ignored", "--test-threads=1"])
        with patch("build_runtime.subprocess.run") as run:
            with self.assertRaises(ValueError):
                test_suite(Path("."), "victory-hle", "mapping_diagnostic_actual_views", env={}, diagnostics=True, expected=1, ignored=True)
            run.assert_not_called()

    def test_default_fails_fast(self):
        with patch("build_runtime.test_suite", side_effect=subprocess.CalledProcessError(1, ["test"])) as suite, patch("build_runtime.run") as run:
            with self.assertRaises(subprocess.CalledProcessError):
                validate_paired(Path("."))
            self.assertEqual(suite.call_count, 1)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
