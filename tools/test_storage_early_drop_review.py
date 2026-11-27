# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact test-only early chained Cow release parity preview.

No production flag or worker edit. Reuses the native-passing codec fixture
unchanged except the call target and nested module import qualification.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = Path("crates/victory-hle/src/modules/dstorage.rs")
FIXTURE_PIN = "807146cc059631a47e5f4c99962d3cf78db8d736"
# Git blob identities of LF-normalized prepared source and exact execute
# slice, reconstructed from upstream 51700c6 plus the two worker-cap edits.
PREPARED_PIN = "bee5b9d71cb8f11c060b798485bd8e68391b36bd"
EXECUTE_PIN = "1b2d667447f5f3f0f94fcc25f224ffb3e1869277"
START = "fn execute(request: &Request) -> Result<(), HRESULT> {"
END = "\n/// Inflates a zlib stream into `out`, returning the bytes written."
OLD = "        packed.truncate(n);\n        Cow::Owned(packed)"
NEW = "        packed.truncate(n);\n        if early_drop {\n            drop(source);\n        }\n        Cow::Owned(packed)"
SIGNATURE = "fn execute_early_drop_review(request: &Request, early_drop: bool) -> Result<(), HRESULT> {"
ANCHOR = "    #[test]\n    fn zlib_then_bcpack() {"
CALL = "        execute(&r)"
IMPORT_OLD = "use super::super::xmem;"
IMPORT_NEW = "use crate::modules::xmem;"
MARKER = "fn execute_early_drop_review("


def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def fixture():
    raw = (ROOT / "probes" / "storage_codec_native.rs").read_bytes()
    if blob_id(raw) != FIXTURE_PIN:
        raise ValueError("historical native codec fixture changed")
    return raw.decode("utf-8")


def execute_slice(source):
    if MARKER in source or source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("execute boundary mismatch")
    begin = source.index(START)
    end = source.index(END, begin)
    return source[begin:end]


def verify_prepared(source, *, source_pin=PREPARED_PIN, execute_pin=EXECUTE_PIN):
    # read_text normalizes CRLF to LF on Windows; do not strip whitespace.
    if blob_id(source.encode("utf-8")) != source_pin:
        raise ValueError("full prepared dstorage source identity mismatch")
    if blob_id(execute_slice(source).encode("utf-8")) != execute_pin:
        raise ValueError("prepared execute identity mismatch")


def clone_execute(source):
    original = execute_slice(source).rstrip()
    if original.count(OLD) != 1:
        raise ValueError("chained Cow anchor mismatch")
    clone = original.replace(START, SIGNATURE, 1).replace(OLD, NEW, 1)
    if clone.replace(SIGNATURE, START, 1).replace(NEW, OLD, 1) != original:
        raise ValueError("clone not reversible")
    return clone


def mode_fixture(fragment, enabled):
    if fragment.count(CALL) != 1 or fragment.count(IMPORT_OLD) != 5:
        raise ValueError("historical fixture call/import mismatch")
    name = "on" if enabled else "off"
    call = "        execute_early_drop_review(&r, " + str(enabled).lower() + ")"
    body = fragment.replace(CALL, call, 1).replace(IMPORT_OLD, IMPORT_NEW)
    if body.replace(call, CALL, 1).replace(IMPORT_NEW, IMPORT_OLD) != fragment:
        raise ValueError("fixture rewrite not reversible")
    return "mod early_drop_" + name + " {\n    use super::*;\n" + body.rstrip() + "\n}\n"


def transform(source, fragment):
    if source.count(ANCHOR) != 1 or "mod early_drop_on {" in source or "mod early_drop_off {" in source:
        raise ValueError("native test insertion anchor mismatch")
    insert = clone_execute(source) + "\n\n"
    insert += (mode_fixture(fragment, False) + "\n" + mode_fixture(fragment, True)).rstrip() + "\n\n"
    proposed = source.replace(ANCHOR, insert + ANCHOR, 1)
    if proposed.replace(insert, "", 1) != source:
        raise ValueError("test-only insertion not reversible")
    return proposed


class StorageEarlyDropReviewTests(unittest.TestCase):
    def example(self):
        return START + "\n" + OLD + "\n}\n" + END + "\n" + ANCHOR + "\n"

    def test_exact_clone_and_reversible_insert(self):
        source = self.example()
        f = fixture()
        clone = clone_execute(source)
        self.assertIn(NEW, clone)
        insert = clone + "\n\n" + (mode_fixture(f, False) + "\n" + mode_fixture(f, True)).rstrip() + "\n\n"
        result = transform(source, f)
        self.assertEqual(result.replace(insert, "", 1), source)
        for invalid in (source.replace(OLD, "", 1), source + ANCHOR, result):
            with self.assertRaises(ValueError):
                transform(invalid, f)

    def test_full_pin_rejects_dependency_and_execute_drift(self):
        source = self.example()
        pins = dict(source_pin=blob_id(source.encode()),
                    execute_pin=blob_id(execute_slice(source).encode()))
        verify_prepared(source, **pins)
        # Even with all clone anchors intact, drift outside the execute
        # function must not be accepted as the reviewed native baseline.
        for changed in (source + "// dependency drift\n",
                        source.replace("}", " }", 1), source + "\n"):
            with self.assertRaisesRegex(ValueError, "full prepared"):
                verify_prepared(changed, **pins)
        with self.assertRaisesRegex(ValueError, "execute identity"):
            verify_prepared(source, source_pin=pins["source_pin"], execute_pin="0" * 40)

    def test_explicit_modes_preserve_six_native_cases(self):
        f = fixture()
        for enabled in (False, True):
            body = mode_fixture(f, enabled)
            self.assertEqual(body.count("#[test]"), 3)
            self.assertEqual(body.count("#[ignore ="), 3)
            self.assertIn("execute_early_drop_review(&r, " + str(enabled).lower() + ")", body)
            self.assertNotIn(IMPORT_OLD, body)
            for name in ("chain_address", "chain_pages", "partial_error"):
                self.assertIn("fn storage_codec_native_" + name + "()", body)
        self.assertEqual(NEW.count("drop(source);"), 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="isolated prepared runtime only")
    args = parser.parse_args()
    path = args.checkout / PATH
    try:
        source = path.read_text(encoding="utf-8")
        verify_prepared(source)
        proposed = transform(source, fixture())
        if args.apply:
            path.write_text(proposed, encoding="utf-8")
        else:
            print("Early drop: full prepared source and execute identities, exact clone and both modes verified")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Early drop preview failed: {exc}\n")


if __name__ == "__main__":
    if "--checkout" in sys.argv:
        main()
    else:
        unittest.main()
