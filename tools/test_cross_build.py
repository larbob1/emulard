# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import unittest
from cross_build import build_command, TARGET

class CrossBuildTests(unittest.TestCase):
    def test_release_build_path(self):
        root = Path("runtime")
        command, binary = build_command(root, False, 2)
        self.assertEqual(command[:3], ["cargo", "xwin", "build"])
        self.assertIn("--release", command)
        self.assertNotIn("--features", command)
        self.assertEqual(command[command.index("--jobs") + 1], "2")
        self.assertEqual(command[command.index("--target-dir") + 1], str(root / "target"))
        self.assertEqual(binary, root / "target" / TARGET / "release" / "victory.exe")

    def test_diagnostics_build_path(self):
        root = Path("runtime")
        command, binary = build_command(root, True, 1)
        self.assertNotIn("--release", command)
        self.assertEqual(command[command.index("--profile") + 1], "diag")
        self.assertEqual(command[command.index("--features") + 1], "diagnostics")
        self.assertEqual(binary, root / "target" / TARGET / "diag" / "victory.exe")

    def test_invalid_job_count(self):
        for n in (0, -1, 65):
            with self.assertRaises(ValueError):
                build_command(Path("runtime"), False, n)

if __name__ == "__main__":
    unittest.main()
