# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_fault_bitmap import SPECS, transform

def model(pages):
    words = {}
    for page in pages:
        word, bit = divmod(page, 32)
        words[word] = words.get(word, 0) | (1 << bit)
    return sorted(word * 32 + bit for word, bits in words.items()
                  for bit in range(32) if bits & (1 << bit))

class FaultBitmapTests(unittest.TestCase):
    def test_old_hash_collision(self):
        self.assertEqual(model([1, 4096, 8191]), [1, 4096, 8191])

    def test_repeated_and_same_word(self):
        self.assertEqual(model([0, 1, 31, 32, 31]), [0, 1, 31, 32])

    def test_source_edits(self):
        for _, _, edits in SPECS:
            data = "\n".join(a for a, _ in edits).encode()
            result = transform(data, edits).decode()
            for _, after in edits:
                self.assertIn(after, result)
                if not after:
                    self.assertNotIn(_, result)

    def test_missing_anchor(self):
        for _, _, edits in SPECS:
            with self.assertRaises(ValueError):
                transform(b"", edits)

if __name__ == "__main__":
    unittest.main()
