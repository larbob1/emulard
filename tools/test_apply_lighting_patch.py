# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from unittest.mock import patch
import apply_lighting_patch as candidate
from apply_memory_patch import blob_hash

PAGE = 65536

def locations(address, count, directory):
    """Reference model only: (view, byte offset) for aligned words."""
    result = []
    for word in range(count):
        page, offset = divmod(address + 4 * word, PAGE)
        view, base = directory.get(page, (0, 0))
        result.append((view, base + offset))
    return result

class LightingTests(unittest.TestCase):
    def test_distinct_views(self):
        self.assertEqual(locations(PAGE - 8, 4, {0: (7, 0), 1: (9, 4096)}),
                         [(7, PAGE - 8), (7, PAGE - 4), (9, 4096), (9, 4100)])

    def test_missing_second_page(self):
        self.assertEqual(locations(PAGE - 4, 2, {0: (7, 0)}),
                         [(7, PAGE - 4), (0, 0)])

    def test_carry_above_four_gib(self):
        self.assertEqual(locations((1 << 32) - 4, 2, {65535: (2, 0), 65536: (3, 0)}),
                         [(2, PAGE - 4), (3, 0)])

    def test_same_view_contiguous(self):
        self.assertEqual(locations(PAGE - 4, 2, {0: (3, 0), 1: (3, PAGE)}),
                         [(3, PAGE - 4), (3, PAGE)])

    def test_all_source_edits(self):
        data = "\n".join(before for before, _ in candidate.EDITS).encode()
        with patch.object(candidate, "EXPECTED", blob_hash(data)):
            result = candidate.patch_source(data).decode()
        for before, after in candidate.EDITS:
            self.assertIn(after, result)
            if before not in after:
                self.assertNotIn(before, result)
            else:
                self.assertEqual(result.count(before), 1)

    def test_revision_rejected(self):
        with self.assertRaises(ValueError):
            candidate.patch_source(b"unknown")

    def test_missing_anchor_rejected(self):
        data = candidate.EDITS[0][0].encode()
        with patch.object(candidate, "EXPECTED", blob_hash(data)):
            with self.assertRaises(ValueError):
                candidate.patch_source(data)

if __name__ == "__main__":
    unittest.main()
