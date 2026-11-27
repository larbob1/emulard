"""Test exact preview wiring; actual native execution is separate."""
import unittest
from preview_hle_pool_native import git_blob
from preview_hle_pool_spawn_failure import (
    ANCHOR, REPLACEMENT, FIXTURE, MARKER, preview,
)


class SpawnFailurePreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = b"prefix\n" + ANCHOR + b"\nsuffix\n"
        self.fixture = FIXTURE.read_bytes()

    def test_exact_reversible_injection(self):
        result = preview(self.source, self.fixture, git_blob(self.source))
        prefix = result[:-(len(self.fixture) + 1)]
        self.assertEqual(prefix.replace(REPLACEMENT, ANCHOR, 1), self.source)
        self.assertEqual(prefix.count(REPLACEMENT), 1)
        self.assertEqual(result.count(MARKER), 1)
        self.assertIn(b"#[cfg(test)]", REPLACEMENT)
        self.assertTrue(REPLACEMENT.endswith(ANCHOR))

    def test_wrong_blob_refused(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            preview(self.source, self.fixture)

    def test_missing_or_duplicate_anchor_refused(self):
        for source in (b"other", self.source + ANCHOR):
            with self.assertRaisesRegex(ValueError, "unique"):
                preview(source, self.fixture, git_blob(source))

    def test_invalid_test_module_refused(self):
        for fixture in (self.fixture.replace(b"#[cfg(test)]", b""), self.fixture * 2):
            with self.assertRaisesRegex(ValueError, "test-only"):
                preview(self.source, fixture, git_blob(self.source))

    def test_fixture_preserves_panic_and_queue_contract(self):
        source = self.fixture.decode()
        for needle in ("catch_unwind", "pool.state.is_poisoned()",
                       "let state = lock(&pool.state)", "state.0.len(), 1",
                       "(1, true)", "(2, true)", "recv_timeout",
                       "spawn_panic_preserves_queued_work"):
            self.assertIn(needle, source)
        self.assertNotIn("clear_poison(", source)


if __name__ == "__main__":
    unittest.main()
