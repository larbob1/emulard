# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_paired_tile_replay import REPLACEMENTS, transform

class PairedReplayPatcherTests(unittest.TestCase):
    def test_anchors(self):
        source = "\n".join(a for a, _ in REPLACEMENTS)
        result = transform(source)
        for a, b in REPLACEMENTS:
            self.assertIn(b, result)
            with self.assertRaises(ValueError):
                transform(source.replace(a, "", 1))

if __name__ == "__main__":
    unittest.main()
