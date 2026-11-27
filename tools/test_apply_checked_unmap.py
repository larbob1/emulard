# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_checked_unmap import PATCHES, transform

class CheckedUnmapTests(unittest.TestCase):
    def test_exact_anchors(self):
        for replacements in PATCHES.values():
            source = "\n".join(old for old, _ in replacements)
            result = transform(source, replacements)
            for old, new in replacements:
                self.assertIn(new, result)
                with self.assertRaises(ValueError):
                    transform(source.replace(old, "", 1), replacements)

if __name__ == "__main__":
    unittest.main()
