"""Exact-source idle clone with a test-only cleanup / handle observation hook."""
import argparse
from pathlib import Path
import unittest

from preview_hle_pool_native import PINNED_BLOB, git_blob
from test_hle_idle_native_preview import (
    STRUCT, STATIC, IMPL, MARKER as OLD_MARKER, preview as clone_preview,
)

FIXTURE = Path(__file__).resolve().parents[1] / "probes" / "hle_idle_cleanup_native.rs"
MARKER = b"mod hle_idle_cleanup_native_review"
SPAWN = b"            std::thread::spawn(move || self.work());"
HOOK = b"            start(self);"


def preview(source, fixture, expected=PINNED_BLOB):
    if MARKER in source or fixture.count(MARKER) != 1 or OLD_MARKER in fixture:
        raise ValueError("expected unique cleanup module")
    original = clone_preview(source, fixture.replace(MARKER, OLD_MARKER, 1), expected)
    prefix = source + b"\n"
    if not original.startswith(prefix):
        raise ValueError("production prefix changed")
    module = original[len(prefix):].replace(OLD_MARKER, MARKER, 1)
    if module.count(SPAWN) != 1 or HOOK in module:
        raise ValueError("expected unique clone spawn anchor")
    return prefix + module.replace(SPAWN, HOOK, 1)


class IdleCleanupPreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = STRUCT + b"\n\n" + STATIC + b"\n\n" + IMPL
        self.fixture = FIXTURE.read_bytes()

    def test_exact_prefix_and_reversible_spawn_hook(self):
        result = preview(self.source, self.fixture, git_blob(self.source))
        prefix = self.source + b"\n"
        self.assertTrue(result.startswith(prefix))
        module = result[len(prefix):]
        self.assertEqual(module.count(MARKER), 1)
        self.assertEqual(module.count(HOOK), 1)
        expected = clone_preview(self.source, self.fixture.replace(MARKER, OLD_MARKER, 1),
                                 git_blob(self.source))[len(prefix):].replace(OLD_MARKER, MARKER, 1)
        self.assertEqual(module.replace(HOOK, SPAWN, 1), expected)

    def test_wrong_source_refuses(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            preview(self.source, self.fixture)

    def test_duplicate_module_refuses(self):
        with self.assertRaises(ValueError):
            preview(self.source, self.fixture * 2, git_blob(self.source))

    def test_fixture_observes_actual_thread_handle(self):
        for needle in (b"impl Drop for Cleanup", b"thread_local!", b"pool.work()",
                       b"WAIT_TIMEOUT", b"WAIT_OBJECT_0", b"GetCurrentThreadId",
                       b"handle.join()", b"retired_worker_cleanup_does_not_supply_capacity"):
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
