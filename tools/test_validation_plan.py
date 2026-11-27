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

    def test_hle_native_exact_plan(self):
        with patch("build_runtime.test_suite") as suite, patch("build_runtime.run") as run:
            validate_paired(Path("."))
        for name, count, ignored in (("xasync::tests::", 7, False),
                ("pool_callbacks_may_wait_for_each_other", 1, False), ("hle_pool_native_review::reentrant_pool_callback_progress", 1, True), ("hle_idle_native_review::idle_native_baseline", 1, True), ("hle_idle_native_review::idle_native_candidate", 1, True), ("hle_idle_boundary_review::empty_wake_then_submission_reuses_idle_worker", 1, True), ("hle_idle_boundary_review::expiry_holds_lock_then_submission_starts_replacement", 1, True), ("hle_idle_cleanup_native_review::retired_worker_cleanup_does_not_supply_capacity", 1, True)):
            selected = [c for c in suite.call_args_list if c.args[1:3] == ("victory-hle", name)]
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0].kwargs["expected"], count)
            self.assertEqual(selected[0].kwargs["ignored"], ignored)
        self.assertEqual(run.call_count, 2)

    def test_hle_native_exact_count(self):
        from build_runtime import test_suite
        names = ("hle_pool_native_review::reentrant_pool_callback_progress", "hle_idle_native_review::idle_native_baseline", "hle_idle_native_review::idle_native_candidate", "hle_idle_boundary_review::empty_wake_then_submission_reuses_idle_worker", "hle_idle_boundary_review::expiry_holds_lock_then_submission_starts_replacement", "hle_idle_cleanup_native_review::retired_worker_cleanup_does_not_supply_capacity")
        for name in names:
            for output, ok in (
                ("test result: ok. 1 passed; 0 failed; 0 ignored;", True),
                ("test result: ok. 0 passed; 0 failed; 0 ignored;", False),
                ("test result: ok. 2 passed; 0 failed; 0 ignored;", False),
                ("test result: ok. 1 passed; 0 failed; 1 ignored;", False),
                ("test result: ok. 1 passed; 0 failed;", False),
                ("test result: ok. 1 passed; 0 failed; 0 ignored;\ntest result: ok. 0 passed; 0 failed; 0 ignored;", False),
            ):
                with self.subTest(name=name, output=output), patch("build_runtime.subprocess.run") as run:
                    run.return_value.stdout = output
                    if ok:
                        test_suite(Path("."), "victory-hle", name, expected=1, ignored=True)
                    else:
                        with self.assertRaises(subprocess.CalledProcessError):
                            test_suite(Path("."), "victory-hle", name, expected=1, ignored=True)
                    self.assertEqual(run.call_args.args[0], ["cargo", "test", "--locked", "-p", "victory-hle", "--lib", name, "--", "--ignored", "--test-threads=1"])
                    self.assertEqual(run.call_args.kwargs["timeout"], 600)
        with patch("build_runtime.subprocess.run") as run:
            for package, name, expected in (("victory-hle", names[0], None), ("victory-hle", "hle_pool", 1), ("victory-gpu", names[0], 1)):
                with self.assertRaises(ValueError):
                    test_suite(Path("."), package, name, expected=expected, ignored=True)
            run.assert_not_called()
        with patch("build_runtime.subprocess.run", side_effect=subprocess.TimeoutExpired("cargo", 600)):
            with self.assertRaises(subprocess.CalledProcessError):
                test_suite(Path("."), "victory-hle", names[0], expected=1, ignored=True)

    def test_default_fails_fast(self):
        with patch("build_runtime.test_suite", side_effect=subprocess.CalledProcessError(1, ["test"])) as suite, patch("build_runtime.run") as run:
            with self.assertRaises(subprocess.CalledProcessError):
                validate_paired(Path("."))
            self.assertEqual(suite.call_count, 1)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
