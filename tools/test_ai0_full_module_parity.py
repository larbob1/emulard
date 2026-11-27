# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate runner safeguards without downloading or vendoring upstream code."""
from pathlib import Path
import shutil
import tempfile
import unittest

from ai0_full_module_parity import (
    CASES, blob, pinned, listing_ok, receipt_ok, run_module,
)


class FullModuleParityTests(unittest.TestCase):
    expected = frozenset({"tests::one", "tests::two"})

    def test_manifest_counts_and_uniqueness(self):
        self.assertEqual([len(c.baseline | {c.candidate}) for c in CASES], [11, 11, 5])
        self.assertEqual(len({c.head for c in CASES}), 3)
        self.assertEqual(len({c.candidate for c in CASES}), 3)

    def test_blob_and_pin(self):
        self.assertEqual(blob(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source"
            path.write_bytes(b"source\n")
            self.assertEqual(pinned(path, blob(b"source\n")), b"source\n")
            with self.assertRaises(ValueError):
                pinned(path, blob(b"source\r\n"))

    def test_discovery_rejects_missing_extra_duplicate(self):
        good = "tests::one: test\ntests::two: test\n\n2 tests, 0 benchmarks\n"
        self.assertTrue(listing_ok(good, self.expected))
        for bad in (good.replace("two", "one"), good.replace("two", "extra"),
                    good.replace("2 tests", "1 test"), good.replace("0 benchmarks", "1 benchmark"),
                    "", good + good):
            self.assertFalse(listing_ok(bad, self.expected))

    def test_receipt_rejects_missing_failed_ignored_or_duplicate(self):
        good = ("test tests::one ... ok\ntest tests::two ... ok\n"
                "test result: ok. 2 passed; 0 failed; 0 ignored; "
                "0 measured; 0 filtered out; finished in 0.00s\n")
        self.assertTrue(receipt_ok(good, self.expected))
        for bad in (good.replace("two", "one"), good.replace("two", "extra"),
                    good.replace("0 failed", "1 failed"), good.replace("0 ignored", "1 ignored"),
                    good.replace("0 filtered", "1 filtered"), good.replace("2 passed", "0 passed"),
                    good.replace("two ... ok", "two ... FAILED"), good + good, ""):
            self.assertFalse(receipt_ok(bad, self.expected))
        self.assertFalse(receipt_ok("", frozenset()))

    def test_reject_contradictory_extra_output(self):
        listing = "tests::one: test\ntests::two: test\n2 tests, 0 benchmarks\n"
        receipt = ("running 2 tests\ntest tests::one ... ok\ntest tests::two ... ok\n"
                   "test result: ok. 2 passed; 0 failed; 0 ignored; "
                   "0 measured; 0 filtered out; finished in 0.00s\n")
        self.assertTrue(listing_ok(listing, self.expected))
        self.assertTrue(receipt_ok(receipt, self.expected))
        for extra in ("extra: benchmark\n", "unexpected output\n", "1 test, 0 benchmarks\n"):
            self.assertFalse(listing_ok(listing + extra, self.expected))
        for extra in ("test tests::extra ... FAILED\n",
                      "test result: FAILED. 0 passed; 1 failed;\n",
                      "unexpected output\n"):
            self.assertFalse(receipt_ok(receipt + extra, self.expected))
            self.assertFalse(receipt_ok(extra + receipt, self.expected))
        self.assertFalse(receipt_ok(receipt.replace("running 2", "running 3"), self.expected))
        self.assertFalse(receipt_ok(receipt.replace("0.00s", "0.00s garbage"), self.expected))

    def test_real_compiler_and_receipt_on_tiny_generated_module(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tiny.rs"
            source.write_text(
                "#[cfg(test)] mod tests { "
                "#[test] fn one() { assert_eq!(1+1,2); } "
                "#[test] fn two() { assert!(true); } }")
            self.assertEqual(run_module(source, root, rustc, self.expected), 2)
            with self.assertRaises(ValueError):
                run_module(source, root, rustc, frozenset({"tests::one"}))


if __name__ == "__main__":
    unittest.main()
