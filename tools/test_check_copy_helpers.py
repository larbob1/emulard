# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from check_copy_helpers import SECTIONS, extract

class PortableCopyExtractionTests(unittest.TestCase):
    def test_exact_sections(self):
        source = "\n".join(a + "\nBODY\n" + b for a,b in SECTIONS)
        result = extract(source)
        self.assertEqual(result.count("BODY"), 2)
        for a,b in SECTIONS:
            self.assertIn(a, result)
            self.assertNotIn(b, result)
            with self.assertRaises(ValueError):
                extract(source.replace(a, "", 1))

if __name__ == "__main__":
    unittest.main()
