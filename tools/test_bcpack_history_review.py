# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only BCPack history and native baseline fixture."""
import argparse
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = Path("crates/victory-formats/src/bcpack.rs")
PIN = "c8d35378df7fab633cc4370a74655b4bd7db9ac7"
ANCHOR = "    #[test]\n    fn the_shipped_tables_parse() {"
MARKER = "fn bcpack_history_native_reference_bounds()"


def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def fixture():
    return (ROOT / "probes" / "bcpack_history_review.rs").read_text(encoding="utf-8")


def transform(source, fragment):
    if source.count(ANCHOR) != 1 or MARKER in source or fragment.count(MARKER) != 1:
        raise ValueError("expected one unapplied history test anchor")
    return source.replace(ANCHOR, fragment.rstrip() + "\n\n" + ANCHOR, 1)


class BcpackHistoryReviewTests(unittest.TestCase):
    def test_reference_bounds_for_every_short_length(self):
        # For a short stream i < blocks < 256. For long streams the
        # capacity and modulo are unchanged. No runtime change implied.
        for blocks in range(1, 256):
            for i in range(blocks):
                self.assertLess(i % 256, blocks)
                # For every 1 <= r <= i, 0 <= i-r <= i-1.
                if i:
                    self.assertLess((i - 1) % 256, blocks)
                    self.assertLess((i - i) % 256, blocks)

    def test_requested_extent(self):
        for blocks in (0, 1, 4, 16, 64, 255, 256, 257, 1024):
            self.assertEqual(min(blocks, 256) * 40, min(blocks * 40, 10240))
        # 40 is illustrative; actual native size_of is reported separately.

    def test_exact_reversible_preview(self):
        code = fixture()
        original = "before\n" + ANCHOR + "\nafter"
        patched = transform(original, code)
        self.assertEqual(patched.replace(code.rstrip() + "\n\n", "", 1), original)
        for invalid in ("", original + ANCHOR, patched):
            with self.assertRaises(ValueError):
                transform(invalid, code)
        self.assertEqual(code.count("#[test]"), 2)
        self.assertEqual(code.count("#[ignore ="), 2)

    def test_git_blob_identity(self):
        self.assertEqual(blob_id(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="isolated prepared runtime only")
    args = parser.parse_args()
    path = args.checkout / PATH
    try:
        raw = path.read_bytes()
        if blob_id(raw) != PIN:
            raise ValueError("pinned BCPack blob mismatch; stop for prepared source review")
        result = transform(raw.decode("utf-8"), fixture())
        if args.apply:
            path.write_bytes(result.encode("utf-8"))
        else:
            print("BCPack history: exact pinned blob and test anchor verified")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"BCPack history preview failed: {exc}\n")


if __name__ == "__main__":
    if "--checkout" in sys.argv:
        main()
    else:
        unittest.main()
