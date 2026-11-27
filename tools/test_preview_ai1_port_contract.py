# SPDX-License-Identifier: GPL-3.0-or-later
import itertools
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import preview_ai1_port_contract as p


class PortContractTests(unittest.TestCase):
    def setUp(self):
        self.shadow = ("prefix\n" + p.CUT[0] + "\nsuffix\n").encode()
        self.texture = ("prefix\n" + p.DETILE[0] + "\nseparator\n" +
                        p.SPREAD[0] + "\nsuffix\n").encode()
        self.sources = {p.SHADOW: self.shadow, p.TEXTURE: self.texture}
        # Synthetic complete source, with independent expected postimages.
        # The real pinned hashes are not modified outside each test.
        self.pre = {k: p.blob(v) for k, v in self.sources.items()}
        self.sh = {False: self.pre[p.SHADOW], True: p.blob(
            self.shadow.replace(p.CUT[0].encode(), p.CUT[1].encode()))}
        self.tx = {}
        for d, s in itertools.product((False, True), repeat=2):
            t = self.texture
            if s:
                t = t.replace(p.SPREAD[0].encode(), p.SPREAD[1].encode())
            if d:
                t = t.replace(p.DETILE[0].encode(), p.DETILE[1].encode())
            self.tx[d, s] = p.blob(t)
        self.addCleanup(patch.stopall)
        patch.object(p, "PREIMAGE", self.pre).start()
        patch.object(p, "SHADOW_HASH", self.sh).start()
        patch.object(p, "TEXTURE_HASH", self.tx).start()

    def test_all_eight_modes_and_no_input_mutation(self):
        original = dict(self.sources)
        for c, d, s in itertools.product((False, True), repeat=3):
            with self.subTest(c=c, d=d, s=s):
                out, receipt = p.calculate(self.sources, c, d, s)
                self.assertEqual(receipt["mode"], {"C": c, "D": d, "S": s})
                self.assertEqual(receipt["postimage_lf"],
                    {p.SHADOW: self.sh[c], p.TEXTURE: self.tx[d, s]})
                self.assertEqual(receipt["would_change"], sorted(
                    ([p.SHADOW] if c else []) + ([p.TEXTURE] if d or s else [])))
                self.assertEqual(self.sources, original)
                if not c:
                    self.assertEqual(out[p.SHADOW], self.shadow)
                if not (d or s):
                    self.assertEqual(out[p.TEXTURE], self.texture)

    def test_control_and_crlf(self):
        out, receipt = p.calculate(self.sources)
        self.assertEqual(out, self.sources)
        self.assertEqual(receipt["would_change"], [])
        crlf = {k: v.replace(b"\n", b"\r\n") for k, v in self.sources.items()}
        self.assertEqual(p.calculate(crlf, True, True, True),
                         p.calculate(self.sources, True, True, True))

    def test_reject_changed_missing_extra_and_mixed_sources(self):
        cases = [
            {**self.sources, p.SHADOW: self.shadow + b"extra"},
            {p.SHADOW: self.shadow},
            {**self.sources, "extra.rs": b""},
            {**self.sources, p.SHADOW: self.shadow.replace(b"\n", b"\r\n", 1)},
            {**self.sources, p.SHADOW: self.shadow + b"\r"},
        ]
        for source in cases:
            with self.assertRaises(ValueError):
                p.calculate(source)

    def test_reject_duplicate_absent_and_applied_anchor(self):
        old, new = p.CUT
        for source in ("", old + "\n" + old, new, old + "\n" + new):
            with self.assertRaises(ValueError):
                p.replace_once(source, p.CUT)

    def test_reject_partial_application(self):
        out, _ = p.calculate(self.sources, True, False, False)
        with self.assertRaises(ValueError):
            p.calculate(out, True, True, True)

    def test_postimage_mismatch(self):
        with patch.dict(p.SHADOW_HASH, {True: "0" * 40}):
            with self.assertRaisesRegex(ValueError, "postimage mismatch"):
                p.calculate(self.sources, True, False, False)

    def test_reject_non_boolean_selection(self):
        for value in (0, 1, "1", None):
            with self.assertRaises(ValueError):
                p.calculate(self.sources, value)

    def test_checkout_preview_is_read_only_and_revision_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in self.sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            with patch.object(p, "git_head", return_value=p.UPSTREAM):
                receipt = p.preview(root, True, True, True)
                self.assertEqual(receipt["would_change"], sorted(self.sources))
            self.assertEqual({name: (root/name).read_bytes() for name in self.sources},
                             self.sources)
            with patch.object(p, "git_head", return_value="wrong"):
                with self.assertRaisesRegex(ValueError, "unsupported upstream"):
                    p.preview(root, True, True, True)


if __name__ == "__main__":
    unittest.main()
