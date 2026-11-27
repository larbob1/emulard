"""Test-only preview plumbing; does not compile the HLE crate."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

from preview_hle_pool_native import FIXTURE, MARKER, PINNED_BLOB, git_blob, preview


class HleNativePreviewTests(unittest.TestCase):
    def test_exact_append_and_production_prefix(self):
        source = b"fn unchanged() {}\n"
        fixture = FIXTURE.read_bytes()
        output = preview(source, fixture, git_blob(source))
        self.assertEqual(output, source + b"\n" + fixture)
        self.assertEqual(output.count(MARKER), 1)

    def test_wrong_source_refuses(self):
        with self.assertRaisesRegex(ValueError, "not the exact"):
            preview(b"unrelated", FIXTURE.read_bytes())

    def test_existing_module_refuses(self):
        source = b"mod hle_pool_native_review {}"
        with self.assertRaisesRegex(ValueError, "already present"):
            preview(source, FIXTURE.read_bytes(), git_blob(source))

    def test_duplicate_fixture_or_missing_test_gate_refuses(self):
        source = b"fn unchanged() {}"
        fixture = FIXTURE.read_bytes()
        for invalid in (fixture + fixture, fixture.replace(b"#[cfg(test)]", b"")):
            with self.assertRaises(ValueError):
                preview(source, invalid, git_blob(source))

    def test_cli_wrong_source_leaves_files_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "xasync.rs"
            output = pathlib.Path(tmp) / "preview.rs"
            source.write_bytes(b"not pinned")
            output.write_bytes(b"existing")
            tool = FIXTURE.parents[0].parent / "tools" / "preview_hle_pool_native.py"
            run = subprocess.run([sys.executable, str(tool), str(source), str(output)],
                                 capture_output=True, timeout=10)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(source.read_bytes(), b"not pinned")
            self.assertEqual(output.read_bytes(), b"existing")

    def test_native_fixture_shape_and_pin(self):
        self.assertEqual(PINNED_BLOB, "068d75f2a8a50b7a4f0ec7a45e9c849c657bcde1")
        fixture = FIXTURE.read_text()
        for required in ("#[ignore", "fn reentrant_pool_callback_progress",
                         "XTaskQueueCreate(1, 0", "Some(parent)", "Some(dependent)",
                         "recv_timeout(LIMIT)", "XTaskQueueCloseHandle"):
            self.assertIn(required, fixture)


if __name__ == "__main__":
    unittest.main()
