"""Preview controlled boundary tests on the exact-source idle pool clone."""
import argparse
from pathlib import Path
import unittest

from preview_hle_pool_native import PINNED_BLOB, git_blob
from test_hle_idle_native_preview import (
    STRUCT, STATIC, IMPL, MARKER as OLD_MARKER, CANDIDATE_WAIT, preview as clone_preview,
)

FIXTURE = Path(__file__).resolve().parents[1] / "probes" / "hle_idle_boundary_review.rs"
MARKER = b"mod hle_idle_boundary_review"
PREDICATE = b"|s| s.0.is_empty()"
OBSERVATION = b"|s| observe_wait(s.0.is_empty())"
DECREMENT = b"                    next.1 -= 1;"
GATE = b"                    after_wait(next.0.len(), next.1);\n" + DECREMENT


def preview(source, fixture, expected=PINNED_BLOB):
    if MARKER in source or fixture.count(MARKER) != 1 or OLD_MARKER in fixture:
        raise ValueError("expected unique boundary module")
    original = clone_preview(source, fixture.replace(MARKER, OLD_MARKER, 1), expected)
    prefix = source + b"\n"
    if not original.startswith(prefix):
        raise ValueError("production prefix changed")
    module = original[len(prefix):].replace(OLD_MARKER, MARKER, 1)
    if module.count(CANDIDATE_WAIT) != 1:
        raise ValueError("expected exact candidate wait")
    if CANDIDATE_WAIT.count(PREDICATE) != 1 or CANDIDATE_WAIT.count(DECREMENT) != 1:
        raise ValueError("expected unique wait hook anchors")
    hooked = CANDIDATE_WAIT.replace(PREDICATE, OBSERVATION, 1).replace(DECREMENT, GATE, 1)
    return prefix + module.replace(CANDIDATE_WAIT, hooked, 1)


class IdleBoundaryPreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = STRUCT + b"\n\n" + STATIC + b"\n\n" + IMPL
        self.fixture = FIXTURE.read_bytes()

    def test_unchanged_prefix_and_reversible_hooks(self):
        result = preview(self.source, self.fixture, git_blob(self.source))
        prefix = self.source + b"\n"
        self.assertTrue(result.startswith(prefix))
        module = result[len(prefix):]
        self.assertEqual(module.count(MARKER), 1)
        self.assertEqual(module.count(OBSERVATION), 1)
        self.assertEqual(module.count(GATE), 1)
        restored = module.replace(OBSERVATION, PREDICATE, 1).replace(GATE, DECREMENT, 1)
        expected = clone_preview(self.source, self.fixture.replace(MARKER, OLD_MARKER, 1),
                                 git_blob(self.source))[len(prefix):].replace(OLD_MARKER, MARKER, 1)
        self.assertEqual(restored, expected)

    def test_wrong_source_refuses(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            preview(self.source, self.fixture)

    def test_duplicate_module_refuses(self):
        with self.assertRaises(ValueError):
            preview(self.source, self.fixture * 2, git_blob(self.source))

    def test_fixture_has_separate_interleavings(self):
        for needle in (b"empty_wake_then_submission_reuses_idle_worker",
                       b"expiry_holds_lock_then_submission_starts_replacement",
                       b"EPOCH.store(1", b"pool.ready.notify_all()", b"until_retired(pool, 2)"):
            self.assertIn(needle, self.fixture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = preview(args.source.read_bytes(), FIXTURE.read_bytes())
    with args.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
