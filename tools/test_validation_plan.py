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

    def test_scatter_batch_matrix(self):
        with patch("build_runtime.test_suite") as suite, patch("build_runtime.run") as run:
            validate_paired(Path("."))
        for name in ("physical_pages_map_alias_and_unmap", "a_read_in_place_never_meets_the_gap_of_a_remapping"):
            calls = [c for c in suite.call_args_list if c.args[1:3] == ("victory-hle", name)
                     and "VICTORY_MAP_SCATTER_LOCK_BATCH" in (c.kwargs.get("env") or {})]
            self.assertEqual([(c.kwargs["env"]["VICTORY_MAP_DIFF"],
                               c.kwargs["env"]["VICTORY_MAP_SCATTER_LOCK_BATCH"]) for c in calls],
                             [("0", "0"), ("0", "1"), ("1", "0"), ("1", "1")])
        self.assertEqual(run.call_count, 2)

    def test_default_fails_fast(self):
        with patch("build_runtime.test_suite", side_effect=subprocess.CalledProcessError(1, ["test"])) as suite, patch("build_runtime.run") as run:
            with self.assertRaises(subprocess.CalledProcessError):
                validate_paired(Path("."))
            self.assertEqual(suite.call_count, 1)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
