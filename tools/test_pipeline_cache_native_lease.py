# SPDX-License-Identifier: GPL-3.0-or-later
"""Title-free sidecar lease feasibility, not a production cache lock.

Linux uses flock; native Windows uses LockFileEx. No mixed-platform
interop, Wine/Proton, network filesystem or hostile-path guarantee.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


def try_lease(file):
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        import msvcrt

        class Overlapped(ctypes.Structure):
            _fields_ = [
                ("Internal", ctypes.c_size_t),
                ("InternalHigh", ctypes.c_size_t),
                ("Offset", wintypes.DWORD),
                ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE),
            ]

        lock = ctypes.WinDLL("kernel32", use_last_error=True).LockFileEx
        lock.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped),
        ]
        lock.restype = wintypes.BOOL
        # Exclusive, fail immediately, one byte at offset zero.
        overlap = Overlapped()
        if lock(msvcrt.get_osfhandle(file.fileno()), 3, 0, 1, 0, ctypes.byref(overlap)):
            return True
        error = ctypes.get_last_error()
        if error == 33:  # ERROR_LOCK_VIOLATION
            return False
        raise ctypes.WinError(error)
    if sys.platform.startswith("linux"):
        import errno
        import fcntl
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                return False
            raise
    raise RuntimeError("unsupported platform")


def worker(directory, marker, mode):
    directory = Path(directory)
    # Never truncate, replace or unlink the persistent sidecar.
    with (directory / "synthetic-cache.lock").open("a+b") as file:
        if not try_lease(file):
            return 75
        (directory / "synthetic-cache.marker").write_bytes(marker.encode("ascii"))
        if mode == "hold":
            sys.stdin.buffer.read(1)
    return 0


@unittest.skipUnless(sys.platform == "win32" or sys.platform.startswith("linux"),
                     "native Windows/Linux file-lock feasibility only")
class NativeCacheLeaseTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.directory = self.root / "cache"
        self.directory.mkdir()
        self.sidecar = self.directory / "synthetic-cache.lock"
        self.sidecar.write_bytes(b"persistent-sidecar")
        self.identity = self.sidecar.stat().st_ino

    def command(self, directory, marker, mode):
        return [sys.executable, str(Path(__file__).resolve()), "--worker",
                str(directory), marker, mode]

    def stop(self, child):
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)

    def owner(self):
        child = subprocess.Popen(
            self.command(self.directory, "owner", "hold"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop, child)
        deadline = time.monotonic() + 5
        marker = self.directory / "synthetic-cache.marker"
        while time.monotonic() < deadline:
            self.assertIsNone(child.poll(), "owner exited before holding lease")
            try:
                if marker.read_bytes() == b"owner":
                    return child
            except (FileNotFoundError, PermissionError):
                pass
            time.sleep(0.01)
        self.fail("owner readiness deadline")

    def contender(self, directory=None, expected=75):
        result = subprocess.run(
            self.command(directory or self.directory, "contender", "once"),
            capture_output=True, timeout=5,
        )
        self.assertEqual(result.returncode, expected, result.stderr)

    def check_sidecar(self):
        # Read the locked byte only after all owners have exited.
        self.assertEqual(self.sidecar.read_bytes(), b"persistent-sidecar")
        self.assertEqual(self.sidecar.stat().st_ino, self.identity)

    def check_owner(self):
        self.assertEqual((self.directory / "synthetic-cache.marker").read_bytes(), b"owner")

    def test_normal_exit_releases_and_busy_does_not_write(self):
        child = self.owner()
        self.contender()
        self.check_owner()
        child.communicate(input=b"x", timeout=5)
        self.assertEqual(child.returncode, 0)
        self.contender(expected=0)
        self.check_sidecar()
        self.assertEqual((self.directory / "synthetic-cache.marker").read_bytes(), b"contender")

    def test_abrupt_exit_releases_without_sidecar_replacement(self):
        child = self.owner()
        self.contender()
        self.check_owner()
        child.kill()  # Only our own synthetic worker.
        child.communicate(timeout=5)
        self.assertNotEqual(child.returncode, 0)
        self.contender(expected=0)
        self.check_sidecar()

    def test_independent_directory_can_publish_while_owner_holds(self):
        child = self.owner()
        other = self.root / "independent"
        other.mkdir()
        self.contender(other, expected=0)
        self.assertEqual((other / "synthetic-cache.marker").read_bytes(), b"contender")
        self.check_owner()
        child.communicate(input=b"x", timeout=5)
        self.assertEqual(child.returncode, 0)
        self.check_sidecar()

    def test_open_error_is_not_classified_as_busy_or_success(self):
        absent = self.root / "absent"
        result = subprocess.run(self.command(absent, "contender", "once"),
                                capture_output=True, timeout=5)
        self.assertNotIn(result.returncode, (0, 75))
        self.assertFalse(absent.exists())
        self.check_sidecar()


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        sys.exit(worker(*sys.argv[2:]))
    unittest.main()
