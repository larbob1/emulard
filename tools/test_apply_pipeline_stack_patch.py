# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

import apply_pipeline_stack_patch as candidate


class PipelineStackPatchTests(unittest.TestCase):
    def test_adds_32_mib_stack_to_unpatched_source(self):
        result = candidate.patch_source(candidate.BEFORE.encode())
        self.assertIn(b".stack_size(32 * 1024 * 1024)", result)
        self.assertNotIn(candidate.BEFORE.encode(), result)

    def test_upgrades_existing_8_mib_stack(self):
        result = candidate.patch_source(candidate.AFTER_8.encode())
        self.assertIn(b".stack_size(32 * 1024 * 1024)", result)
        self.assertNotIn(b".stack_size(8 * 1024 * 1024)", result)

    def test_is_idempotent(self):
        result = candidate.patch_source(candidate.AFTER.encode())
        self.assertEqual(result, candidate.AFTER.encode())

    def test_rejects_unknown_source(self):
        with self.assertRaises(ValueError):
            candidate.patch_source(b"unrecognized source")


if __name__ == "__main__":
    unittest.main()
