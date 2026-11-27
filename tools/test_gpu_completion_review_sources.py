# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit checks of the read-only gate; not a prepared runtime receipt."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import check_gpu_completion_review_sources as gate


class GPUCompletionSourceReviewTests(unittest.TestCase):
    def test_git_blob_known_value_and_crlf_normalization(self):
        self.assertEqual(gate.blob_id(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        self.assertEqual(gate.blob_id(b"a\r\nb\r\n"), gate.blob_id(b"a\nb\n"))
        self.assertNotEqual(gate.blob_id(b"a\rb"), gate.blob_id(b"a\nb"))

    def test_five_fixed_source_identities(self):
        self.assertEqual(set(gate.PINS), {
            gate.PREFIX + name for name in ("host.rs", "shadow.rs", "texback.rs", "queue2.rs", "list.rs")
        })
        self.assertEqual(len(set(gate.PINS.values())), 5)
        for digest in gate.PINS.values():
            self.assertRegex(digest, r"^[0-9a-f]{40}$")

    def test_matching_bytes_and_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "host.rs"
            path.write_bytes(b"anchor\r\nbody\r\n")
            pins = {"host.rs": gate.blob_id(b"anchor\nbody\n")}
            self.assertEqual(gate.verify(root, pins), [("host.rs", pins["host.rs"], True)])
            path.write_bytes(b"anchor\nchanged body\n")
            before = path.read_bytes()
            self.assertEqual(gate.verify(root, pins), [("host.rs", gate.blob_id(before), False)])
            self.assertEqual(path.read_bytes(), before)

    def test_missing_and_unreadable_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "directory.rs").mkdir()
            pins = {name: gate.blob_id(b"") for name in ("missing.rs", "directory.rs")}
            self.assertEqual(gate.verify(root, pins), [(name, None, False) for name in pins])

    def test_mismatch_returns_nonzero_and_reports_all_fixed_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(gate.main([directory]), 1)
            receipt = output.getvalue()
            self.assertIn("gate: refused", receipt)
            self.assertEqual(receipt.count("MISMATCH"), 5)
            for name in gate.PINS:
                self.assertIn(name + " MISMATCH unreadable", receipt)
            self.assertNotIn(directory, receipt)

    def test_outside_checkout_symlink_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.rs"
            outside.write_bytes(b"data")
            checkout = root / "checkout"
            checkout.mkdir()
            try:
                (checkout / "host.rs").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            self.assertEqual(gate.verify(checkout, {"host.rs": gate.blob_id(b"data")}),
                             [("host.rs", None, False)])
