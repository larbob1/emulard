# SPDX-License-Identifier: GPL-3.0-or-later
"""Compose original codec tests and exact early-drop review in an isolated runtime."""
import argparse
from pathlib import Path
import unittest
import test_storage_codec_native as codec
import test_storage_early_drop_review as early

def compose(source):
    # Verify pristine prepared identity BEFORE either test-only insertion.
    early.verify_prepared(source)
    fragment = early.fixture()
    original = codec.transform(source, fragment)
    # The original marker would reject insertion after the nested clones.
    return early.transform(original, fragment)

class StorageEarlyDropCompositionTests(unittest.TestCase):
    def test_composition(self):
        from unittest.mock import patch
        source = early.StorageEarlyDropReviewTests().example()
        with patch.object(early, "verify_prepared", wraps=early.verify_prepared) as check:
            # An example is not the pinned prepared source; must fail closed.
            with self.assertRaisesRegex(ValueError, "full prepared"):
                compose(source)
            check.assert_called_once_with(source)
        with patch.object(early, "verify_prepared") as check:
            out = compose(source)
            check.assert_called_once_with(source)
        self.assertEqual(out.count("mod early_drop_off {"), 1)
        self.assertEqual(out.count("mod early_drop_on {"), 1)
        self.assertEqual(out.count("#[ignore ="), 9)
        self.assertEqual(out.count("fn execute_early_drop_review("), 1)
        self.assertEqual(out.count(early.ANCHOR), 1)
        self.assertEqual(out.count(early.CALL), 1)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    path = args.checkout / early.PATH
    try:
        proposed = compose(path.read_text(encoding="utf-8"))
        if args.apply:
            path.write_text(proposed, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Storage early drop composition failed: {exc}\n")

if __name__ == "__main__":
    main()
