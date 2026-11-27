# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only native raw file scratch clone, no production policy."""
import argparse
from pathlib import Path
import sys
import unittest

from test_storage_early_drop_review import execute_slice, verify_prepared

ROOT = Path(__file__).resolve().parents[1]
PATH = Path("crates/victory-hle/src/modules/dstorage.rs")
START = "fn execute(request: &Request) -> Result<(), HRESULT> {"
SIGNATURE = "fn execute_scratch_review(request: &Request, scratch: &mut NativeScratch) -> Result<(), HRESULT> {"
OLD = "            let mut data = vec![0; size];\n            read_into(request, &mut data)?;\n            out.copy_from_slice(&data);\n            Ok(size)"
NEW = "            scratch.run(size, |data| {\n                read_into(request, data)?;\n                out.copy_from_slice(data);\n                Ok(size)\n            })"
ANCHOR = "    #[test]\n    fn raw_and_zlib_reads_from_a_file() {"
MARKER = "fn execute_scratch_review("


def fixture():
    return (ROOT / "probes" / "storage_scratch_native.rs").read_text(encoding="utf-8")


def clone_execute(source):
    if MARKER in source:
        raise ValueError("scratch clone already exists")
    original = execute_slice(source).rstrip()
    if original.count(OLD) != 1:
        raise ValueError("raw bounce anchor mismatch")
    candidate = original.replace(START, SIGNATURE, 1).replace(OLD, NEW, 1)
    if candidate.replace(SIGNATURE, START, 1).replace(NEW, OLD, 1) != original:
        raise ValueError("scratch clone not reversible")
    return candidate


def transform(source, fragment):
    if source.count(ANCHOR) != 1 or MARKER in source:
        raise ValueError("scratch test insertion anchor mismatch")
    insert = clone_execute(source) + "\n\n" + fragment.rstrip() + "\n\n"
    result = source.replace(ANCHOR, insert + ANCHOR, 1)
    if result.replace(insert, "", 1) != source:
        raise ValueError("test-only insertion not reversible")
    return result


class StorageScratchNativeTests(unittest.TestCase):
    def test_reversible_clone_and_insert(self):
        from test_storage_early_drop_review import END
        source = START + "\n" + OLD + "\n}\n" + END + "\n" + ANCHOR
        f = fixture()
        clone = clone_execute(source)
        proposed = transform(source, f)
        self.assertEqual(proposed.replace(clone + "\n\n" + f.rstrip() + "\n\n", "", 1), source)
        self.assertIn(NEW, clone)
        for invalid in (source.replace(OLD, ""), source + ANCHOR, proposed):
            with self.assertRaises(ValueError):
                transform(invalid, f)

    def test_scope(self):
        f = fixture()
        self.assertEqual(f.count("#[test]"), 2)
        self.assertEqual(f.count("#[ignore ="), 2)
        for item in ("read_into(request, data)?", "out.copy_from_slice(data)", "scratch.run(size"):
            self.assertIn(item, NEW)
        self.assertNotIn("thread_local", f)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    path = args.checkout / PATH
    try:
        source = path.read_text(encoding="utf-8")
        verify_prepared(source)
        result = transform(source, fixture())
        if args.apply:
            path.write_text(result, encoding="utf-8")
        else:
            print("Native scratch: exact prepared identity and reversible test-only clone verified")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Native scratch preview failed: {exc}\n")


if __name__ == "__main__":
    if "--checkout" in sys.argv:
        main()
    else:
        unittest.main()
