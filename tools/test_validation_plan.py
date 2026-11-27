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

    def test_shader_cache_fresh_modes(self):
        with patch("build_runtime.test_suite") as suite, patch("build_runtime.run") as run:
            validate_paired(Path("."))
        for name, ignored in (("shader_cache_reuse_actual_equivalence", True), ("shader_cache_publication_failure_keeps_runtime_translation", False)):
            selected = [c for c in suite.call_args_list if c.args[1:3] == ("victory-gpu", name)]
            self.assertEqual(len(selected), 2)
            self.assertEqual([c.kwargs["env"]["VICTORY_SHADER_CACHE_REUSE_TRANSLATED"] for c in selected], ["0", "1"])
            for c in selected:
                self.assertEqual(c.kwargs["expected"], 1)
                self.assertEqual(c.kwargs["ignored"], ignored)
        selected = [c for c in suite.call_args_list if c.args[1:3] == ("victory-gpu", "entries_round_trip_and_reject_damage")]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].kwargs["expected"], 1)
        self.assertEqual(run.call_count, 2)

    def test_shader_cache_count_and_explicit_switch(self):
        from build_runtime import test_suite
        for mode in ("0", "1"):
            env = {"VICTORY_SHADER_CACHE_REUSE_TRANSLATED": mode}
            for output, ok in (("test result: ok. 1 passed; 0 failed;", True),
                               ("test result: ok. 0 passed; 0 failed;", False),
                               ("test result: ok. 2 passed; 0 failed;", False),
                               ("test result: ok. 1 passed; 0 failed;\ntest result: ok. 0 passed; 0 failed;", False)):
                with self.subTest(mode=mode, output=output), patch("build_runtime.subprocess.run") as run:
                    run.return_value.stdout = output
                    if ok:
                        test_suite(Path("."), "victory-gpu", "shader_cache_reuse_actual_equivalence", env=env, expected=1, ignored=True)
                    else:
                        with self.assertRaises(subprocess.CalledProcessError):
                            test_suite(Path("."), "victory-gpu", "shader_cache_reuse_actual_equivalence", env=env, expected=1, ignored=True)
                    self.assertEqual(run.call_args.args[0], ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib",
                        "shader_cache_reuse_actual_equivalence", "--", "--ignored", "--test-threads=1"])
        with patch("build_runtime.subprocess.run") as run:
            with self.assertRaises(ValueError):
                test_suite(Path("."), "victory-gpu", "shader_cache_reuse_actual_equivalence", env={}, expected=1, ignored=True)
            run.assert_not_called()

    def test_default_fails_fast(self):
        with patch("build_runtime.test_suite", side_effect=subprocess.CalledProcessError(1, ["test"])) as suite, patch("build_runtime.run") as run:
            with self.assertRaises(subprocess.CalledProcessError):
                validate_paired(Path("."))
            self.assertEqual(suite.call_count, 1)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
