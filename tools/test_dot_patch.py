# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_dot_patch import SPECS, transform

def dot4(a, b, acc, signed, duplicate=False):
    if duplicate:
        a = (a >> 16) | (a & 0xffff0000)
    def lane(word, i):
        v = (word >> (8*i)) & 255
        return v - 256 if signed and v >= 128 else v
    return (acc + sum(lane(a,i)*lane(b,i) for i in range(4))) & 0xffffffff

class PackedDotTests(unittest.TestCase):
    def test_signed_unsigned(self):
        self.assertEqual(dot4(0xffffffff,0x01010101,0,True),0xfffffffc)
        self.assertEqual(dot4(0xffffffff,0x01010101,0,False),1020)

    def test_overflow_and_selection(self):
        self.assertEqual(dot4(0x01010101,0x01010101,0xffffffff,False),3)
        self.assertEqual(dot4(0x01020304,0x01010101,0,True,True),6)

    def test_unique_anchor(self):
        for _,_,edits in SPECS:
            for before,after in edits:
                self.assertEqual(transform(before.encode(),[(before,after)]).decode(),after)
                with self.assertRaises(ValueError):
                    transform((before+before).encode(),[(before,after)])

if __name__ == "__main__":
    unittest.main()
