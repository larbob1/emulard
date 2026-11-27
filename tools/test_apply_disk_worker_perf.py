# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_disk_worker_perf import REPLACEMENTS, transform

class DiskWorkerPatcherTests(unittest.TestCase):
    def test_anchors_and_reject_mismatch(self):
        source = "\n".join(old for old, _ in REPLACEMENTS)
        result = transform(source)
        for old, new in REPLACEMENTS:
            self.assertIn(new, result)
            with self.assertRaises(ValueError):
                transform(source.replace(old, "", 1))
            with self.assertRaises(ValueError):
                transform(source + "\n" + old)

if __name__ == "__main__":
    unittest.main()
