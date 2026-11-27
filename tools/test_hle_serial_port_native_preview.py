"""Append a baseline serialized port test to the exact pinned xasync source."""
import argparse
from pathlib import Path
import unittest
from preview_hle_pool_native import PINNED_BLOB, git_blob

FIXTURE = Path(__file__).resolve().parents[1] / "probes" / "hle_serial_port_native.rs"
MARKER = b"mod hle_serial_port_native_review"
ANCHORS = (
    b"if mode == Mode::Serialized {",
    b"match worker.take(1000, || false) {",
    b"None if Arc::strong_count(&worker) == 1 => break,",
    b"fn XTaskQueueCreateComposite(",
    b"fn XTaskQueueCloseHandle(",
)


def preview(source, fixture, expected=PINNED_BLOB):
    if git_blob(source) != expected:
        raise ValueError("not exact pinned xasync.rs")
    if any(source.count(anchor) != 1 for anchor in ANCHORS):
        raise ValueError("missing or duplicate serialized port anchor")
    if MARKER in source or fixture.count(MARKER) != 1 or fixture.count(b"#[cfg(test)]") != 1:
        raise ValueError("expected one new test-only module")
    return source + b"\n" + fixture


class SerialPortNativePreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = b"\n".join(ANCHORS)
        self.fixture = FIXTURE.read_bytes()

    def test_exact_append(self):
        result = preview(self.source, self.fixture, git_blob(self.source))
        self.assertEqual(result, self.source + b"\n" + self.fixture)

    def test_wrong_blob_refused(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            preview(self.source, self.fixture)

    def test_missing_duplicate_anchors_refused(self):
        for source in (self.source.replace(ANCHORS[0], b""), self.source + ANCHORS[1]):
            with self.assertRaisesRegex(ValueError, "anchor"):
                preview(source, self.fixture, git_blob(source))

    def test_bad_module_refused(self):
        for fixture in (self.fixture * 2, self.fixture.replace(b"#[cfg(test)]", b"")):
            with self.assertRaisesRegex(ValueError, "test-only"):
                preview(self.source, fixture, git_blob(self.source))

    def test_fixture_shared_ownership_and_release_receipt(self):
        for needle in (b"Mode::Serialized", b"XTaskQueueCreateComposite",
                       b"XTaskQueueCloseHandle(original)", b"XTaskQueueCloseHandle(composite)",
                       b"weak_port.strong_count()", b"RELEASED.load",
                       b"shared_serial_port_drains_after_last_queue_close"):
            self.assertIn(needle, self.fixture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = preview(args.source.read_bytes(), FIXTURE.read_bytes())
    with args.output.open("xb") as out:
        out.write(result)


if __name__ == "__main__":
    main()
