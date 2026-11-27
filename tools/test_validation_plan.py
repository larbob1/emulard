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

    def test_storage_codec_exact_plan(self):
        with patch("build_runtime.test_suite") as suite, patch("build_runtime.run") as run:
            validate_paired(Path("."))
        for name, ignored in (("zlib_then_bcpack", False), ("zlib_into_pages_in_place_and_across_allocations", False), ("zlib_inflate_handles_short_exact_empty_and_bad_streams", False), ("storage_codec_native_chain_address", True), ("storage_codec_native_chain_pages", True), ("storage_codec_native_partial_error", True)):
            selected = [c for c in suite.call_args_list if c.args[1:3] == ("victory-hle", name)]
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0].kwargs["expected"], 1)
            self.assertEqual(selected[0].kwargs["ignored"], ignored)
        self.assertEqual(run.call_count, 2)

    def test_storage_codec_exact_count(self):
        from build_runtime import test_suite
        for name in ("storage_codec_native_chain_address", "storage_codec_native_chain_pages", "storage_codec_native_partial_error"):
            for output, ok in (("test result: ok. 1 passed; 0 failed;", True),
                               ("test result: ok. 0 passed; 0 failed;", False),
                               ("test result: ok. 2 passed; 0 failed;", False),
                               ("test result: ok. 1 passed; 0 failed;\ntest result: ok. 0 passed; 0 failed;", False)):
                with self.subTest(name=name, output=output), patch("build_runtime.subprocess.run") as run:
                    run.return_value.stdout = output
                    if ok:
                        test_suite(Path("."), "victory-hle", name, expected=1, ignored=True)
                    else:
                        with self.assertRaises(subprocess.CalledProcessError):
                            test_suite(Path("."), "victory-hle", name, expected=1, ignored=True)
                    self.assertEqual(run.call_args.args[0], ["cargo", "test", "--locked", "-p", "victory-hle", "--lib",
                        name, "--", "--ignored", "--test-threads=1"])
        with patch("build_runtime.subprocess.run") as run:
            for name, expected in (("storage_codec_native_", 3), ("storage_codec_native_chain_address", None)):
                with self.assertRaises(ValueError):
                    test_suite(Path("."), "victory-hle", name, expected=expected, ignored=True)
            run.assert_not_called()

    def test_default_fails_fast(self):
        with patch("build_runtime.test_suite", side_effect=subprocess.CalledProcessError(1, ["test"])) as suite, patch("build_runtime.run") as run:
            with self.assertRaises(subprocess.CalledProcessError):
                validate_paired(Path("."))
            self.assertEqual(suite.call_count, 1)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
