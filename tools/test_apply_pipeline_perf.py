# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_pipeline_perf import PATCHES, transform

class PipelinePerfTests(unittest.TestCase):
    def test_all_anchors(self):
        for replacements in PATCHES.values():
            source = "\n".join(old for old, _ in replacements)
            result = transform(source, replacements)
            for _, new in replacements:
                self.assertIn(new, result)

    def test_fail_closed(self):
        for replacements in PATCHES.values():
            source = "\n".join(old for old, _ in replacements)
            for old, _ in replacements:
                with self.assertRaises(ValueError):
                    transform(source.replace(old, "", 1), replacements)
                with self.assertRaises(ValueError):
                    transform(source + "\n" + old, replacements)

if __name__ == "__main__":
    unittest.main()
