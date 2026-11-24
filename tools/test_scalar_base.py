# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from unittest.mock import patch
from apply_memory_patch import blob_hash
import apply_lighting_patch as candidate

def split_address(lo, hi, displacement, immediate):
    total = lo + displacement
    high = (hi + (total >> 32)) & 0xffffffff
    low = total & 0xffffffff
    return (((high << 32) | low) + immediate) & 0xffffffffffffffff

class ScalarBaseTests(unittest.TestCase):
    def test_unsigned_offset_carry(self):
        self.assertEqual(split_address(0xffffffff, 0, 1, 0), 1 << 32)
        self.assertEqual(split_address(0, 2, 0xffffffff, 0), 0x2ffffffff)

    def test_signed_immediate_borrow(self):
        self.assertEqual(split_address(0, 1, 0, -4), 0xfffffffc)
        self.assertEqual(split_address(0xffffffff, 0, 1, -1), 0xffffffff)

    def test_scalar_only_selection(self):
        source = "\n".join(a for a, _ in candidate.EDITS).encode()
        with patch.object(candidate, "EXPECTED", blob_hash(source)):
            result = candidate.patch_source(source, scalar_only=True).decode()
        for _, replacement in candidate.SCALAR_EDITS:
            self.assertIn(replacement, result)
        for anchor, _ in candidate.EDITS[len(candidate.SCALAR_EDITS):]:
            self.assertIn(anchor, result)

    def test_wrong_revision(self):
        with self.assertRaises(ValueError):
            candidate.patch_source(b"wrong revision", scalar_only=True)

if __name__ == "__main__":
    unittest.main()
