"""Compose exact pinned idle-retirement test modules without changing production."""
import argparse
from pathlib import Path
import unittest
from preview_hle_pool_native import PINNED_BLOB, git_blob
import test_hle_idle_native_preview as idle
import test_hle_idle_boundary_preview as boundary
import test_hle_idle_cleanup_preview as cleanup

MODULES = (
    (idle, "5b3f288530cbe0f81b41b5ee0f5c0a0600f23f43"),
    (boundary, "fe75e62951cb5dc9cb368fbb2957513f1cc01052"),
    (cleanup, "1c5b96a55d170f631079247a4660e59ddb96abae"),
)


def preview(source, fixtures, expected=PINNED_BLOB, modules=MODULES):
    if git_blob(source) != expected:
        raise ValueError("not exact pinned xasync.rs")
    if len(fixtures) != len(modules):
        raise ValueError("incorrect fixture count")
    prefix = source + b"\n"
    parts = []
    for (generator, digest), fixture in zip(modules, fixtures):
        if git_blob(fixture) != digest:
            raise ValueError("fixture digest mismatch")
        candidate = generator.preview(source, fixture, expected)
        if not candidate.startswith(prefix):
            raise ValueError("production prefix changed")
        part = candidate[len(prefix):]
        if part.count(generator.MARKER) != 1 or part.count(b"#[cfg(test)]") != 1:
            raise ValueError("invalid test module")
        if any(other.MARKER in part for other, _ in modules if other is not generator):
            raise ValueError("unexpected sibling module")
        parts.append(part)
    result = prefix + b"\n".join(parts)
    for generator, _ in modules:
        if result.count(generator.MARKER) != 1:
            raise ValueError("duplicate or absent module")
    return result


def fixtures():
    return tuple(generator.FIXTURE.read_bytes() for generator, _ in MODULES)


class IdleSuitePreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = idle.STRUCT + b"\n\n" + idle.STATIC + b"\n\n" + idle.IMPL
        self.expected = git_blob(self.source)
        self.fixtures = fixtures()

    def test_exact_pins(self):
        self.assertEqual(tuple(git_blob(f) for f in self.fixtures),
                         tuple(digest for _, digest in MODULES))

    def test_composition_preserves_all_individual_postimages(self):
        prefix = self.source + b"\n"
        result = preview(self.source, self.fixtures, self.expected)
        self.assertTrue(result.startswith(prefix))
        parts = [g.preview(self.source, f, self.expected)[len(prefix):]
                 for (g, _), f in zip(MODULES, self.fixtures)]
        self.assertEqual(result, prefix + b"\n".join(parts))
        for g, _ in MODULES:
            self.assertEqual(result.count(g.MARKER), 1)

    def test_wrong_source_and_fixture_count_refused(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            preview(self.source, self.fixtures)
        with self.assertRaisesRegex(ValueError, "fixture count"):
            preview(self.source, self.fixtures[:-1], self.expected)

    def test_fixture_change_and_reordering_refused(self):
        for altered in ((self.fixtures[0] + b"\n", *self.fixtures[1:]),
                        tuple(reversed(self.fixtures))):
            with self.assertRaisesRegex(ValueError, "digest"):
                preview(self.source, altered, self.expected)

    def test_controlled_release_receipts(self):
        self.assertEqual(self.fixtures[1].count(b"RELEASED.load"), 2)
        self.assertIn(b"RELEASED.store(wait.recv_timeout", self.fixtures[1])
        self.assertIn(b"RELEASED.store(rx.recv_timeout", self.fixtures[2])
        self.assertIn(b"RELEASED.load", self.fixtures[2])
        self.assertEqual(self.fixtures[2].count(b"}, WAIT_TIMEOUT);"), 3)

    def test_five_fresh_process_cases(self):
        cases = (
            b"idle_native_baseline", b"idle_native_candidate",
            b"empty_wake_then_submission_reuses_idle_worker",
            b"expiry_holds_lock_then_submission_starts_replacement",
            b"retired_worker_cleanup_does_not_supply_capacity",
        )
        result = preview(self.source, self.fixtures, self.expected)
        for case in cases:
            self.assertEqual(result.count(b"fn " + case + b"("), 1)
        self.assertEqual(result.count(b"#[ignore ="), 5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = preview(args.source.read_bytes(), fixtures())
    with args.output.open("xb") as out:
        out.write(result)


if __name__ == "__main__":
    main()
