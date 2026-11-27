# SPDX-License-Identifier: GPL-3.0-or-later
"""Title-free validation runner contract tests."""
import unittest
from unittest.mock import patch

import validate_ai1_compare_first_slice as v


class CompareValidationTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(v.normalized(b"a\r\nb\r\n"), b"a\nb\n")
        self.assertEqual(v.normalized(b"a\nb\n"), b"a\nb\n")
        for bad in (b"a\r\nb\n", b"a\rb\n"):
            with self.assertRaises(ValueError):
                v.normalized(bad)

    def test_exact_preimage_guard(self):
        raw = b"original\n"
        with patch.object(v, "RAW_BLOB", v.blob(raw)), patch.object(
                v, "transform", lambda s: s + "prepared\n"):
            self.assertEqual(v.validated_preimage(raw, b"original\r\nprepared\r\n"),
                             "original\nprepared\n")
            for bad in (b"original\n", b"original\nprepared\nextra\n"):
                with self.assertRaises(ValueError):
                    v.validated_preimage(raw, bad)
            with self.assertRaises(ValueError):
                v.validated_preimage(b"wrong\n", b"original\nprepared\n")

    def test_fixture_is_narrow_and_fail_closed(self):
        original = v.OLD + "\n" + v.ANCHOR + "\n}\n"
        baseline = v.fixture_source(original, False)
        fixed = v.fixture_source(original, True)
        self.assertEqual(baseline.count(v.OLD), 1)
        self.assertEqual(fixed.count(v.NEW), 1)
        self.assertEqual(fixed.replace(v.NEW, v.OLD), baseline)
        for bad in (original + original, original + v.MARKER,
                    original.replace(v.OLD, "changed"),
                    original.replace(v.ANCHOR, "changed")):
            with self.assertRaises(ValueError):
                v.fixture_source(bad, True)

    def test_success_requires_exact_nonempty_receipt(self):
        out = (f"test {v.NAME} ... ok\n"
               "test result: ok. 1 passed; 0 failed; 0 ignored; "
               "0 measured; 17 filtered out; finished in 0.1s\n")
        self.assertTrue(v.receipt(out, 0))
        self.assertFalse(v.receipt(out, 1))
        for bad in ("", out.replace(v.NAME, "other::test"),
                    out.replace("1 passed", "0 passed"),
                    out.replace("0 ignored", "1 ignored"), out + out):
            self.assertFalse(v.receipt(bad, 0))

    def test_baseline_requires_expected_panic_site(self):
        out = (f"test {v.NAME} ... FAILED\n"
               "thread panicked at crates/victory-gpu/src/shadow.rs:123:17:\n"
               "attempt to subtract with overflow\n"
               "test result: FAILED. 0 passed; 1 failed; 0 ignored; "
               "0 measured; 17 filtered out; finished in 0.1s\n")
        self.assertTrue(v.receipt(out, 101, baseline_line=123))
        self.assertFalse(v.receipt(out, 0, baseline_line=123))
        self.assertFalse(v.receipt(out, 101, baseline_line=124))
        for bad in (out.replace("attempt to subtract with overflow", "WARP unavailable"),
                    out.replace(v.NAME, "other::test"), out + out):
            self.assertFalse(v.receipt(bad, 101, baseline_line=123))


if __name__ == "__main__":
    unittest.main()
