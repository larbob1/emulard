# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_alias_index import PATCHES, transform

class AliasIndexPatcherTests(unittest.TestCase):
    def test_all_anchors(self):
        for pairs in PATCHES.values():
            source = "\n".join(old for old, _ in pairs)
            result = transform(source, pairs)
            for old, new in pairs:
                self.assertIn(new, result)
                with self.assertRaises(ValueError):
                    transform(source.replace(old, "", 1), pairs)
                with self.assertRaises(ValueError):
                    transform(source + "\n" + old, pairs)

if __name__ == "__main__":
    unittest.main()
