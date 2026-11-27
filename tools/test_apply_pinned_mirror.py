# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_pinned_mirror import REPLACEMENTS, transform

class PinnedMirrorPatcherTests(unittest.TestCase):
    def test_anchors(self):
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
