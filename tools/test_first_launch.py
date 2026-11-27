# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from first_launch import is_x64_pe, run_probe

class FirstLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "probe.exe"

    def fixture(self, machine=0x8664, magic=0x20B):
        buf = bytearray(90)
        buf[:2] = b"MZ"
        struct.pack_into("<I", buf, 60, 64)
        buf[64:68] = b"PE\0\0"
        struct.pack_into("<H", buf, 68, machine)
        struct.pack_into("<H", buf, 88, magic)
        self.path.write_bytes(buf)

    def test_valid_header(self):
        self.fixture()
        self.assertTrue(is_x64_pe(self.path))

    def test_wrong_machine(self):
        self.fixture(machine=0x14C)
        self.assertFalse(is_x64_pe(self.path))

    def test_wrong_magic(self):
        self.fixture(magic=0x10B)
        self.assertFalse(is_x64_pe(self.path))

    def test_missing_file_not_executed(self):
        with patch("first_launch.subprocess.run") as run:
            self.assertEqual(run_probe("wine", self.path, [], 5), "missing-or-invalid-x64-pe")
            run.assert_not_called()

    def test_timeout_report(self):
        self.fixture()
        with patch("first_launch.subprocess.run", side_effect=subprocess.TimeoutExpired("probe", 5)):
            self.assertEqual(run_probe("wine", self.path, [], 5), "timed-out")

    def test_version_only(self):
        self.fixture()
        with patch("first_launch.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(run_probe("wine", self.path, ["--version"], 5), "passed")
            self.assertEqual(run.call_args.args[0][-1], "--version")

if __name__ == "__main__":
    unittest.main()
