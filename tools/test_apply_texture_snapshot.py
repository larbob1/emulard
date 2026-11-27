# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from apply_texture_snapshot import PATCHES, transform

class TextureSnapshotTests(unittest.TestCase):
    def test_all_anchors(self):
        for replacements in PATCHES.values():
            source = "\n".join(old for old, _ in replacements)
            result = transform(source, replacements)
            for _, new in replacements:
                self.assertIn(new, result)

    def test_fail_closed_on_missing_or_duplicate(self):
        for replacements in PATCHES.values():
            source = "\n".join(old for old, _ in replacements)
            for old, _ in replacements:
                with self.assertRaises(ValueError):
                    transform(source.replace(old, "", 1), replacements)
                with self.assertRaises(ValueError):
                    transform(source + "\n" + old, replacements)

    def test_guard_is_released_before_processing(self):
        source = next(new for _, new in PATCHES["crates/victory-gpu/src/texture.rs"] if "drop(_mapped)" in new)
        self.assertLess(source.index("read_into(self.memory, read)"), source.index("drop(_mapped)"))
        self.assertLess(source.index("drop(_mapped)"), source.index("blake3::hash(read)"))
        self.assertLess(source.index("drop(_mapped)"), source.index("self.detile(read)"))

if __name__ == "__main__":
    unittest.main()
