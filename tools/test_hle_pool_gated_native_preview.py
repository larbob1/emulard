"""Test exact test-only preview wiring; native execution is separate."""
import unittest
from preview_hle_pool_native import git_blob
from preview_hle_pool_gated_native import (
    ANCHOR, REPLACEMENT, FIXTURE, MARKER, preview,
)


class GatedPreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = b"prefix\n" + ANCHOR + b"\nsuffix\n"
        self.fixture = FIXTURE.read_bytes()

    def test_exact_reversible_edit(self):
        result = preview(self.source, self.fixture, git_blob(self.source))
        self.assertTrue(result.endswith(b"\n" + self.fixture))
        prefix = result[:-(len(self.fixture) + 1)]
        self.assertEqual(prefix.replace(REPLACEMENT, ANCHOR, 1), self.source)
        self.assertEqual(prefix.count(REPLACEMENT), 1)
        self.assertEqual(result.count(MARKER), 1)
        self.assertIn(b"#[cfg(test)]", REPLACEMENT)
        self.assertIn(b"self.work()", REPLACEMENT)

    def test_refuses_wrong_blob(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            preview(self.source, self.fixture)

    def test_refuses_missing_or_duplicate_anchor(self):
        for source in (b"other", self.source + ANCHOR):
            with self.assertRaisesRegex(ValueError, "unique"):
                preview(source, self.fixture, git_blob(source))

    def test_refuses_missing_test_guard_or_duplicate_module(self):
        for fixture in (self.fixture.replace(b"#[cfg(test)]", b""), self.fixture * 2):
            with self.assertRaisesRegex(ValueError, "test-only"):
                preview(self.source, fixture, git_blob(self.source))

    def test_fixture_uses_actual_pool_and_holds_third_start(self):
        source = self.fixture.decode()
        for needle in ("pool.submit(Task::new", "wait_idle(pool, 1)",
                       "pending.send", "redundant.send", "wait_idle(pool, 3)",
                       "recv_timeout", "pending_start_and_idle_notification"):
            self.assertIn(needle, source)
        self.assertLess(source.index("pending.send"), source.index("redundant.send"))


if __name__ == "__main__":
    unittest.main()
