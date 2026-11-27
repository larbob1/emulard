# SPDX-License-Identifier: GPL-3.0-or-later
"""Linux-only process lease feasibility probe; not runtime or Proton proof.

All children use private synthetic directories and communicate through pipes.
The sidecar is never removed; closing the last handle releases the lease.
"""
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest

WORKER = r'''
import errno
import fcntl
from pathlib import Path
import sys

directory = Path(sys.argv[1])
marker = sys.argv[2].encode("ascii")
hold = sys.argv[3] == "hold"
with (directory / "synthetic-cache.lock").open("a+b") as lease:
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno not in (errno.EACCES, errno.EAGAIN):
            raise
        sys.exit(75)
    (directory / "synthetic-cache.marker").write_bytes(marker)
    if hold:
        print("ready", flush=True)
        sys.stdin.buffer.read(1)
'''


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux flock probe only")
class PipelineCacheLeaseProbeTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.directory = self.root / "cache"
        self.directory.mkdir()

    def command(self, directory, marker, mode):
        return [sys.executable, "-c", WORKER, str(directory), marker, mode]

    def stop(self, child):
        # Only the fixture's own subprocess; no host or title processes.
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)

    def owner(self):
        child = subprocess.Popen(
            self.command(self.directory, "owner", "hold"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop, child)
        readable, _, _ = select.select([child.stdout], [], [], 5)
        self.assertTrue(readable, "synthetic owner did not signal readiness")
        self.assertEqual(child.stdout.readline(), b"ready\n")
        return child

    def contender(self, directory=None, marker="contender", expected=75):
        result = subprocess.run(
            self.command(directory or self.directory, marker, "once"),
            capture_output=True, timeout=5,
        )
        self.assertEqual(result.returncode, expected, result.stderr)

    def check_marker(self, marker):
        self.assertEqual(
            (self.directory / "synthetic-cache.marker").read_bytes(),
            marker.encode("ascii"),
        )

    def test_live_owner_refuses_contender_then_normal_exit_releases(self):
        owner = self.owner()
        sidecar = self.directory / "synthetic-cache.lock"
        identity = sidecar.stat().st_ino
        self.contender()
        self.check_marker("owner")
        owner.communicate(input=b"x", timeout=5)
        self.assertEqual(owner.returncode, 0)
        self.contender(expected=0)
        self.check_marker("contender")
        self.assertEqual(sidecar.stat().st_ino, identity)

    def test_abrupt_child_exit_releases_without_unlink(self):
        owner = self.owner()
        sidecar = self.directory / "synthetic-cache.lock"
        identity = sidecar.stat().st_ino
        self.contender()
        self.check_marker("owner")
        owner.kill()
        owner.communicate(timeout=5)
        self.assertNotEqual(owner.returncode, 0)
        self.contender(expected=0)
        self.check_marker("contender")
        self.assertEqual(sidecar.stat().st_ino, identity)

    def test_directory_symlink_alias_cannot_bypass_same_sidecar(self):
        owner = self.owner()
        alias = self.root / "alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        self.contender(directory=alias)
        self.check_marker("owner")
        owner.communicate(input=b"x", timeout=5)
        self.assertEqual(owner.returncode, 0)
        self.contender(directory=alias, expected=0)
        self.check_marker("contender")

    def test_distinct_directories_do_not_share_lease(self):
        owner = self.owner()
        other = self.root / "other"
        other.mkdir()
        self.contender(directory=other, marker="other", expected=0)
        self.assertEqual((other / "synthetic-cache.marker").read_bytes(), b"other")
        self.check_marker("owner")
        owner.communicate(input=b"x", timeout=5)
        self.assertEqual(owner.returncode, 0)


if __name__ == "__main__":
    unittest.main()
