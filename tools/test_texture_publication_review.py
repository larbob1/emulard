# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_texture_snapshot import PATCHES
from propose_texture_publication import OLD, OLD_END, preview

class TexturePublicationReviewTests(unittest.TestCase):
    def setUp(self):
        self.source = next(new for _, new in PATCHES["crates/victory-gpu/src/texture.rs"]
                           if "drop(_mapped)" in new)

    def test_exact_existing_patch(self):
        changed = preview(self.source)
        self.assertLess(changed.index("drop(_mapped)"), changed.index("blake3::hash(read)"))
        self.assertLess(changed.index("blake3::hash(read)"), changed.index("let Some(publication)"))
        self.assertLess(changed.index("let Some(publication)"), changed.index("mapping_epoch() != epoch"))
        self.assertLess(changed.index("mapping_epoch() != epoch"), changed.index("last.hash = Some(hash)"))
        self.assertLess(changed.index("last.hash = Some(hash)"), changed.index("self.detile(read)"))
        self.assertLess(changed.index("self.detile(read)"), changed.rindex("drop(publication)"))
        self.assertNotIn("let retry = crate::watch::mapping_epoch()", changed)

    def test_refusal_precedes_staging_mutation(self):
        changed = preview(self.source)
        check = changed[changed.index("let Some(publication)"):changed.index("last.hash = Some(hash)")]
        self.assertEqual(check.count("last.asked = 0;"), 2)
        self.assertEqual(check.count("return size;"), 2)
        self.assertNotIn("self.detile", check)
        self.assertNotIn("last.hash =", check)
        self.assertNotIn("title_memory_reading()", check)

    def test_drift_and_double_application_rejected(self):
        for anchor in (OLD, OLD_END):
            with self.assertRaises(ValueError):
                preview(self.source.replace(anchor, "", 1))
            with self.assertRaises(ValueError):
                preview(self.source + anchor)
        with self.assertRaises(ValueError):
            preview(preview(self.source))

if __name__ == "__main__":
    unittest.main()
