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

    def test_warp_fixture_is_separate_and_exact(self):
        with patch("build_runtime.test_suite") as suite, patch("build_runtime.run") as run:
            validate_paired(Path("."))
        selected = [c for c in suite.call_args_list if c.kwargs.get("ignored")]
        self.assertEqual(len(selected), 2)
        self.assertEqual([call.args[1:3] for call in selected], [
            ("victory-gpu", "heap_recording_observation_same_frame_refresh_and_skip"), ("victory-gpu", "detached_list_keeps_recording_after_title_reset")])
        for call in selected:
            self.assertEqual(call.kwargs["env"]["VICTORY_D3D12_WARP"], "1")
            self.assertTrue(call.kwargs["diagnostics"])
            self.assertEqual(call.kwargs["expected"], 1)
        self.assertEqual(run.call_count, 2)

    def test_warp_invocation_and_exact_count(self):
        from build_runtime import test_suite
        for name in ("heap_recording_observation_same_frame_refresh_and_skip", "detached_list_keeps_recording_after_title_reset"):
            env = {"VICTORY_D3D12_WARP": "1"}
            for output, ok in (
                ("test result: ok. 1 passed; 0 failed; 0 ignored;", True),
                ("test result: ok. 0 passed; 0 failed; 1 ignored;", False),
                ("test result: ok. 2 passed; 0 failed;", False),
                ("test result: ok. 1 passed; 0 failed;\ntest result: ok. 0 passed; 0 failed;", False),
                ("test result: FAILED. 1 passed; 1 failed;", False),
            ):
                with self.subTest(output=output), patch("build_runtime.subprocess.run") as run:
                    run.return_value.stdout = output
                    if ok:
                        test_suite(Path("."), "victory-gpu", name, env=env, diagnostics=True, expected=1, ignored=True)
                    else:
                        with self.assertRaises(subprocess.CalledProcessError):
                            test_suite(Path("."), "victory-gpu", name, env=env, diagnostics=True, expected=1, ignored=True)
                    self.assertEqual(run.call_args.args[0], ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib",
                        "--features", "diagnostics", name, "--", "--ignored", "--test-threads=1"])
            with patch("build_runtime.subprocess.run") as run:
                for bad_env, diag, count in (({}, True, 1), (env, False, 1), (env, True, None)):
                    with self.assertRaises(ValueError):
                        test_suite(Path("."), "victory-gpu", name, env=bad_env, diagnostics=diag, expected=count, ignored=True)
                run.assert_not_called()

    def test_default_fails_fast(self):
        with patch("build_runtime.test_suite", side_effect=subprocess.CalledProcessError(1, ["test"])) as suite, patch("build_runtime.run") as run:
            with self.assertRaises(subprocess.CalledProcessError):
                validate_paired(Path("."))
            self.assertEqual(suite.call_count, 1)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
