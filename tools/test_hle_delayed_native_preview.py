"""Test preview wiring only, not native delayed delivery."""
import unittest
from preview_hle_pool_native import git_blob
from preview_hle_delayed_native import ANCHOR, REPLACEMENT, FIXTURE, MARKER, preview


class DelayedNativePreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = b"prefix\n" + ANCHOR + b"\nsuffix"
        self.fixture = FIXTURE.read_bytes()

    def test_reversible_test_gate(self):
        result = preview(self.source, self.fixture, git_blob(self.source))
        prefix = result[:-(len(self.fixture) + 1)]
        self.assertEqual(prefix.replace(REPLACEMENT, ANCHOR, 1), self.source)
        self.assertEqual(result.count(MARKER), 1)
        self.assertIn(b"#[cfg(test)]", REPLACEMENT)
        self.assertLess(REPLACEMENT.index(b"sleep("), REPLACEMENT.index(b"before_deliver()"))
        self.assertLess(REPLACEMENT.index(b"before_deliver()"), REPLACEMENT.index(b"queue.deliver("))

    def test_wrong_blob(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            preview(self.source, self.fixture)

    def test_missing_duplicate_anchor(self):
        for source in (b"other", self.source + ANCHOR):
            with self.assertRaisesRegex(ValueError, "unique"):
                preview(source, self.fixture, git_blob(source))

    def test_invalid_module(self):
        for fixture in (self.fixture.replace(b"#[cfg(test)]", b""), self.fixture * 2):
            with self.assertRaisesRegex(ValueError, "test-only"):
                preview(self.source, fixture, git_blob(self.source))

    def test_fixture_lifetime_and_termination(self):
        for needle in (b"Arc::downgrade", b"drop(q)", b"XTaskQueueTerminate",
                       b"E_ABORT", b"XTaskQueueDispatch", b"XTaskQueueRegisterMonitor",
                       b"delayed_queue_lifetime_and_termination", b"recv_timeout"):
            self.assertIn(needle, self.fixture)


if __name__ == "__main__":
    unittest.main()
