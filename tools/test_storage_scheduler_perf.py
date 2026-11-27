# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_storage_scheduler_perf import REPLACEMENTS, blob_id, transform, verify_prepared
from test_storage_scheduler_review import OLD


class StorageSelectorPatcherTests(unittest.TestCase):
    def test_exact_anchors_and_refuse_repeat(self):
        source = "\n".join(old for old, _ in REPLACEMENTS)
        patched = transform(source)
        for old, new in REPLACEMENTS:
            self.assertIn(new, patched)
            with self.assertRaises(ValueError):
                transform(source.replace(old, "", 1))
            with self.assertRaises(ValueError):
                transform(source + "\n" + old)
        with self.assertRaises(ValueError):
            transform(patched)

    def test_exact_prepared_identity_and_reversal(self):
        source = "\n".join(old for old, _ in REPLACEMENTS)
        pin = blob_id(source)
        verify_prepared(source, pin)
        with self.assertRaisesRegex(ValueError, "full prepared"):
            verify_prepared(source + "\n// unrelated drift", pin)
        restored = transform(source)
        for old, new in reversed(REPLACEMENTS):
            restored = restored.replace(new, old, 1)
        self.assertEqual(restored, source)

    def test_timing_receipt_shape(self):
        fixture = REPLACEMENTS[3][1]
        for key in ('["empty", "sparse", "dense"]', "const WARMUP: usize = 256",
                    "repeat={}", "selected={}", "empty={}", "elapsed_ns={}"):
            self.assertIn(key, fixture)
        self.assertEqual(5 * 3 * 5 * 2, 150)

    def test_default_path_retained(self):
        old, new = REPLACEMENTS[2]
        self.assertIn(OLD, old)
        self.assertIn(OLD, new)
        self.assertIn("unwrap_or(false)", new)
        self.assertIn("let (class, id) = self.select_lane(single_pass)?;", new)
        self.assertTrue(new.endswith("let lane = self.lanes.get_mut(&id)?;"))
        self.assertIn('v == "1"', REPLACEMENTS[1][1])


if __name__ == "__main__":
    unittest.main()
