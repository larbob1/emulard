# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_mapping_hotpath import PATCHES, transform

class MappingHotpathTests(unittest.TestCase):
    def test_exact_anchors(self):
        for pairs in PATCHES.values():
            source = "\n".join(a for a, _ in pairs)
            result = transform(source, pairs)
            for a, b in pairs:
                self.assertIn(b, result)
                with self.assertRaises(ValueError):
                    transform(source.replace(a, "", 1), pairs)
                with self.assertRaises(ValueError):
                    transform(source + "\n" + a, pairs)

if __name__ == "__main__":
    unittest.main()
