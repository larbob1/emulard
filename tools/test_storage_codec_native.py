# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only native codec fragment preview; no shared build registration."""
import argparse
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = Path("crates/victory-hle/src/modules/dstorage.rs")
ANCHOR = "    #[test]\n    fn zlib_then_bcpack() {"
MARKER = "fn storage_codec_native_chain_address()"


def transform(source, fragment):
    if source.count(ANCHOR) != 1 or MARKER in source:
        raise ValueError("expected one unapplied native codec test anchor")
    if fragment.count(MARKER) != 1:
        raise ValueError("missing or duplicate native codec fixture")
    # The fragment remains inside the original cfg(test) module, before
    # an existing test; it does not replace or edit any runtime symbols.
    return source.replace(ANCHOR, fragment.rstrip() + "\n\n" + ANCHOR, 1)


def fixture():
    return (ROOT / "probes" / "storage_codec_native.rs").read_text(encoding="utf-8")


class StorageCodecNativePreviewTests(unittest.TestCase):
    def test_anchor_and_repeat_refusal(self):
        src = "before\n" + ANCHOR + "\nafter"
        code = fixture()
        patched = transform(src, code)
        self.assertEqual(patched.replace(code.rstrip() + "\n\n", "", 1), src)
        for bad in ("", src + ANCHOR, patched):
            with self.assertRaises(ValueError):
                transform(bad, code)

    def test_three_ignored_native_cases(self):
        code = fixture()
        self.assertEqual(code.count("#[test]"), 3)
        self.assertEqual(code.count("#[ignore ="), 3)
        for name in ("chain_address", "chain_pages", "partial_error"):
            self.assertIn("fn storage_codec_native_" + name + "()", code)
        self.assertIn("execute(&r)", code)
        self.assertIn("inflate(&bad, &mut oracle)", code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="only an isolated prepared runtime")
    args = parser.parse_args()
    path = args.checkout / PATH
    try:
        proposed = transform(path.read_text(encoding="utf-8"), fixture())
        if args.apply:
            path.write_text(proposed, encoding="utf-8")
        else:
            print("Native codec fixture: exact test anchor verified (no writes)")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Native codec fixture failed: {exc}\n")


if __name__ == "__main__":
    if "--checkout" in sys.argv:
        main()
    else:
        unittest.main()
