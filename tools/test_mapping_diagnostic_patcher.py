# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_mapping_diagnostic import REPLACEMENTS, transform

class MappingDiagnosticPatcherTests(unittest.TestCase):
    def test_exact_anchors_and_refusal(self):
        source = "\n\n".join(old for old, _, count in REPLACEMENTS for _ in range(count))
        result = transform(source)
        self.assertIn("PhysicalGuard", result)
        self.assertIn("mapping_diagnostic_actual_views", result)
        for old, _, count in REPLACEMENTS:
            with self.subTest(anchor=old[:40]):
                with self.assertRaises(ValueError):
                    transform(source.replace(old, "", 1))
                with self.assertRaises(ValueError):
                    transform(source + "\n" + old)
