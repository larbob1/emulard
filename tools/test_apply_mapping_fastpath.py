# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_mapping_fastpath import REPLACEMENTS, transform

class MappingFastPathTests(unittest.TestCase):
    def test_all_anchors(self):
        source = "\n".join(old for old, _ in REPLACEMENTS)
        result = transform(source)
        for _, new in REPLACEMENTS:
            self.assertIn(new, result)

    def test_missing_or_duplicate_anchor_fails_closed(self):
        source = "\n".join(old for old, _ in REPLACEMENTS)
        for old, _ in REPLACEMENTS:
            with self.assertRaises(ValueError):
                transform(source.replace(old, "", 1))
            with self.assertRaises(ValueError):
                transform(source + "\n" + old)

if __name__ == "__main__":
    unittest.main()
