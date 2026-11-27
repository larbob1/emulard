# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_gpu_copy_perf import REPLACEMENTS, transform

class GPUCopyPerfTests(unittest.TestCase):
    def test_all_anchors(self):
        source = "\n".join(old for old, _ in REPLACEMENTS)
        result = transform(source)
        for _, new in REPLACEMENTS:
            self.assertIn(new, result)

    def test_fail_closed(self):
        source = "\n".join(old for old, _ in REPLACEMENTS)
        for old, _ in REPLACEMENTS:
            with self.assertRaises(ValueError):
                transform(source.replace(old, "", 1))
            with self.assertRaises(ValueError):
                transform(source + "\n" + old)

if __name__ == "__main__":
    unittest.main()
