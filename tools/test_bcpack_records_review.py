# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate an exact, test-only BCPack decoder clone for review."""
import argparse
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = Path("crates/victory-formats/src/bcpack.rs")
PIN = "c8d35378df7fab633cc4370a74655b4bd7db9ac7"
START = "pub fn decode(bc: u8, src: &[u8], dst: &mut [u8], tables: &Tables) -> Result<(), Error> {"
END = "\n// Lanes."
OLD = "    let mut records = vec![0u8; blocks * stride];\n    let mut next = src.iter().copied();\n    lanes(tables, widths, per, blocks, |_| next.next(), &mut records)?;"
NEW = "    let len = blocks * stride;\n    let mut stack;\n    let mut heap;\n    let records = if len <= 4096 {\n        stack = [0u8; 4096];\n        &mut stack[..len]\n    } else {\n        heap = vec![0u8; len];\n        &mut heap[..]\n    };\n    let mut next = src.iter().copied();\n    lanes(tables, widths, per, blocks, |_| next.next(), records)?;"
ANCHOR = "    #[test]\n    fn the_shipped_tables_parse() {"
MARKER = "fn bcpack_records_candidate("


def blob_id(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def fixture():
    return (ROOT / "probes" / "bcpack_records_review.rs").read_text(encoding="utf-8")


def clone_decoder(source):
    if source.count(START) != 1 or source.count(END) != 1 or MARKER in source:
        raise ValueError("decoder boundary drift")
    start = source.index(START)
    end = source.index(END, start)
    original = source[start:end].rstrip()
    if original.count(OLD) != 1:
        raise ValueError("record allocation anchor drift")
    candidate = original.replace("pub fn decode(", MARKER, 1).replace(OLD, NEW, 1)
    if candidate.replace(MARKER, "pub fn decode(", 1).replace(NEW, OLD, 1) != original:
        raise ValueError("decoder clone not reversible")
    return candidate


def transform(source, fragment):
    if source.count(ANCHOR) != 1 or MARKER in source:
        raise ValueError("native test insertion anchor drift")
    clone = clone_decoder(source)
    return source.replace(ANCHOR, clone + "\n\n" + fragment.rstrip() + "\n\n" + ANCHOR, 1)


class BcpackRecordsReviewTests(unittest.TestCase):
    def example(self):
        return START + "\n" + OLD + "\n}\n" + END + "\n" + ANCHOR + "\n"

    def test_exact_clone_and_reversible_insertion(self):
        source = self.example()
        fragment = fixture()
        clone = clone_decoder(source)
        self.assertIn(NEW, clone)
        result = transform(source, fragment)
        self.assertEqual(result.replace(clone + "\n\n" + fragment.rstrip() + "\n\n", "", 1), source)
        for invalid in (source.replace(OLD, ""), source + ANCHOR, result):
            with self.assertRaises(ValueError):
                transform(invalid, fragment)

    def test_layout_thresholds(self):
        for stride in (12, 24, 32):
            edge = 4096 // stride
            self.assertLessEqual(edge * stride, 4096)
            self.assertGreater((edge + 1) * stride, 4096)
        self.assertEqual(fixture().count("#[test]"), 2)
        self.assertEqual(fixture().count("#[ignore ="), 2)

    def test_no_unsafe_or_retained_storage_in_candidate(self):
        self.assertNotIn("unsafe", NEW)
        self.assertNotIn("thread_local", NEW)
        self.assertIn("stack = [0u8; 4096]", NEW)
        self.assertIn("heap = vec![0u8; len]", NEW)
        self.assertIn("lanes(tables, widths, per, blocks", NEW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="isolated prepared runtime only")
    args = parser.parse_args()
    path = args.checkout / PATH
    try:
        raw = path.read_bytes()
        if blob_id(raw) != PIN:
            raise ValueError("pinned BCPack blob mismatch; stop for prepared review")
        proposed = transform(raw.decode("utf-8"), fixture())
        if args.apply:
            path.write_bytes(proposed.encode("utf-8"))
        else:
            print("BCPack records: exact test-only decoder clone verified")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"BCPack records preview failed: {exc}\n")


if __name__ == "__main__":
    if "--checkout" in sys.argv:
        main()
    else:
        unittest.main()
