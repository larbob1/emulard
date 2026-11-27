# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only native file-read fixture, after existing worker-cap preparation."""
import argparse
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = Path("crates/victory-hle/src/modules/dstorage.rs")
ANCHOR = "    #[test]\n    fn raw_and_zlib_reads_from_a_file() {"
MARKER = "fn storage_file_native_bounce_and_eof()"
READ_ANCHOR = "match file.seek_read(&mut out[done..], request.offset + done as u64) {"
BOUNCE_ANCHOR = "read_into(request, &mut data)?;\n            out.copy_from_slice(&data);"


def fixture():
    return (ROOT / "probes" / "storage_file_read_native.rs").read_text(encoding="utf-8")


def transform(source, fragment):
    for anchor in (ANCHOR, READ_ANCHOR, BOUNCE_ANCHOR):
        if source.count(anchor) != 1:
            raise ValueError("expected one pinned file-read anchor: " + anchor[:80])
    if MARKER in source or fragment.count(MARKER) != 1:
        raise ValueError("missing or already installed fixture")
    return source.replace(ANCHOR, fragment.rstrip() + "\n\n" + ANCHOR, 1)


class StorageFileNativePreviewTests(unittest.TestCase):
    def test_exact_reversible_insertion(self):
        source = "\n".join((READ_ANCHOR, BOUNCE_ANCHOR, ANCHOR))
        fragment = fixture()
        proposed = transform(source, fragment)
        self.assertEqual(proposed.replace(fragment.rstrip() + "\n\n", "", 1), source)
        for anchor in (READ_ANCHOR, BOUNCE_ANCHOR, ANCHOR):
            for invalid in (source.replace(anchor, "", 1), source + anchor):
                with self.assertRaises(ValueError):
                    transform(invalid, fragment)
        with self.assertRaises(ValueError):
            transform(proposed, fragment)

    def test_two_ignored_actual_runtime_cases(self):
        source = fixture()
        self.assertEqual(source.count("#[test]"), 2)
        self.assertEqual(source.count("#[ignore ="), 2)
        for symbol in ("read_into(&r", "execute(&r)", "read_source(&r)",
                       "std::thread::scope", "END_OF_FILE"):
            self.assertIn(symbol, source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="isolated prepared runtime only")
    args = parser.parse_args()
    path = args.checkout / PATH
    try:
        proposed = transform(path.read_text(encoding="utf-8"), fixture())
        if args.apply:
            path.write_text(proposed, encoding="utf-8")
        else:
            print("Storage file fixture: three exact anchors verified (no writes)")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Storage file fixture failed: {exc}\n")


if __name__ == "__main__":
    if "--checkout" in sys.argv:
        main()
    else:
        unittest.main()
