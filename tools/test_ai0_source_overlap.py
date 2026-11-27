"""Synthetic tests for the independent source overlap triage helper."""
import contextlib
from hashlib import sha256
import io
from pathlib import Path
import tempfile
import unittest

from ai0_source_overlap import (
    MAX_BYTES, MAX_LINES, Edit, analyze, main, touches,
)


class SourceOverlapTests(unittest.TestCase):
    base = b"a\nb\nc\nd\n"

    def inspect(self, left, right, base=None):
        base = self.base if base is None else base
        return analyze(base, left, right, sha256(base).hexdigest())

    def test_unchanged_and_one_side(self):
        self.assertEqual(self.inspect(self.base, self.base)[0], "UNCHANGED")
        self.assertEqual(self.inspect(b"x\nb\nc\nd\n", self.base)[0],
                         "ONE_SIDE_ONLY")

    def test_disjoint_is_still_review(self):
        result = self.inspect(b"x\nb\nc\nd\n", b"a\nb\ny\nd\n")
        self.assertEqual(result[0], "SAME_FILE_REVIEW")
        self.assertEqual(result[4], [])

    def test_conflicting_replacement(self):
        status, _, _, _, pairs = self.inspect(b"x\nb\nc\nd\n", b"y\nb\nc\nd\n")
        self.assertEqual(status, "OVERLAP_REVIEW")
        self.assertEqual([(a.start, a.end, b.start, b.end, same)
                          for a, b, same in pairs], [(0, 1, 0, 1, False)])

    def test_identical_edit_still_review(self):
        x = b"a\nx\nc\nd\n"
        result = self.inspect(x, x)
        self.assertEqual(result[0], "OVERLAP_REVIEW")
        self.assertTrue(result[4][0][2])

    def test_insertion_same_boundary(self):
        result = self.inspect(b"a\nx\nb\nc\nd\n", b"a\ny\nb\nc\nd\n")
        self.assertEqual(result[0], "OVERLAP_REVIEW")
        self.assertEqual(result[4][0][0].start, 1)
        self.assertEqual(result[4][0][0].end, 1)

    def test_insert_at_deleted_span_edges(self):
        for right in (b"a\nx\nb\nc\nd\n", b"a\nb\nc\nx\nd\n"):
            with self.subTest(right=right):
                self.assertEqual(self.inspect(b"a\nd\n", right)[0],
                                 "OVERLAP_REVIEW")

    def test_adjacent_replacements_not_overlap(self):
        self.assertEqual(self.inspect(b"x\nb\nc\nd\n", b"a\ny\nc\nd\n")[0],
                         "SAME_FILE_REVIEW")

    def test_empty_and_eof_insert(self):
        self.assertEqual(self.inspect(b"a\n", b"b\n", b"")[0], "OVERLAP_REVIEW")
        self.assertEqual(self.inspect(self.base + b"x\n", self.base + b"y\n")[0],
                         "OVERLAP_REVIEW")

    def test_line_endings_and_missing_newline_are_not_normalized(self):
        self.assertEqual(self.inspect(b"a\r\nb\nc\nd\n", self.base)[0],
                         "ONE_SIDE_ONLY")
        self.assertEqual(self.inspect(self.base[:-1], self.base)[0], "ONE_SIDE_ONLY")

    def test_bad_base_identity(self):
        for digest in ("x", "0" * 64):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                analyze(self.base, self.base, self.base, digest)

    def test_invalid_text_or_limits(self):
        for bad in (b"\xff", b"\x00", b"a" * (MAX_BYTES + 1),
                    b"a\n" * (MAX_LINES + 1)):
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                self.inspect(bad, self.base)

    def test_sweep_matches_pairwise_oracle(self):
        base = b"".join(f"{i}\n".encode() for i in range(12))
        lines = base.splitlines(keepends=True)
        variants = []
        for i in range(len(lines) + 1):
            variants.append(b"".join(lines[:i] + [b"insert\n"] + lines[i:]))
            if i < len(lines):
                variants.append(b"".join(lines[:i] + [b"replace\n"] + lines[i+1:]))
                variants.append(b"".join(lines[:i] + lines[i+2:]))
        for left in variants:
            for right in variants:
                _, _, a, b, observed = self.inspect(left, right, base)
                expected = [(x, y, x == y) for x in a for y in b if touches(x, y)]
                self.assertEqual(observed, expected)

    def test_cli_exit_and_no_content_or_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = [Path(temp) / name for name in ("base", "left", "right")]
            for p, data in zip(paths, (self.base, b"SECRET\nb\nc\nd\n", b"y\nb\nc\nd\n")):
                p.write_bytes(data)
            args = [str(p) for p in paths] + ["--base-sha256", sha256(self.base).hexdigest()]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(args), 1)
            self.assertIn("status=OVERLAP_REVIEW", out.getvalue())
            self.assertNotIn("SECRET", out.getvalue())
            self.assertNotIn(temp, out.getvalue())
            paths[2].unlink()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 2)


if __name__ == "__main__":
    unittest.main()
