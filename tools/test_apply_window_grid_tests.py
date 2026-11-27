# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_window_grid_tests import OLD, NEW, transform

class WindowGridPatchTests(unittest.TestCase):
    def test_one_exact_test_only_anchor(self):
        source = "#[cfg(test)]\nmod window_tests {\n" + OLD + "\n}"
        self.assertEqual(transform(source), source.replace(OLD, NEW))
        for invalid in ("", source + OLD, transform(source)):
            with self.assertRaises(ValueError):
                transform(invalid)

if __name__ == "__main__":
    unittest.main()
