"""Validate composition and pins, not actual native execution."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

import preview_hle_native_suite as suite


class NativeSuitePreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = b"prefix\n" + suite.SPAWN + b"\n" + suite.delayed.ANCHOR + b"\nsuffix\n"
        self.fixtures = suite.load_fixtures()

    def make(self, source=None, fixtures=None):
        source = self.source if source is None else source
        fixtures = self.fixtures if fixtures is None else fixtures
        return suite.preview(source, fixtures, suite.api.git_blob(source))

    def test_reversible_composition_and_unchanged_fixtures(self):
        result = self.make()
        suffix = b"".join(b"\n" + fixture for fixture in self.fixtures)
        self.assertTrue(result.endswith(suffix))
        prefix = result[:-len(suffix)]
        self.assertEqual(prefix.replace(suite.COMPOSED, suite.SPAWN, 1).replace(
            suite.delayed.REPLACEMENT, suite.delayed.ANCHOR, 1), self.source)
        for module in suite.MODULES:
            self.assertEqual(result.count(module.MARKER), 1)

    def test_spawn_hooks_order(self):
        self.assertLess(suite.COMPOSED.index(b"before_spawn()"),
                        suite.COMPOSED.index(b"std::thread::spawn"))
        self.assertLess(suite.COMPOSED.index(b"std::thread::spawn"),
                        suite.COMPOSED.index(b"before_work()"))
        self.assertLess(suite.COMPOSED.index(b"before_work()"),
                        suite.COMPOSED.index(b"self.work()"))
        self.assertEqual(suite.COMPOSED.count(b"#[cfg(test)]"), 2)

    def test_wrong_source_and_anchor_refusal(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            suite.preview(self.source, self.fixtures)
        for bad in (b"other", self.source + suite.SPAWN, self.source + suite.delayed.ANCHOR):
            with self.assertRaisesRegex(ValueError, "unique"):
                self.make(source=bad)

    def test_fixture_tamper_and_reorder_refusal(self):
        altered = list(self.fixtures)
        altered[0] += b"\n"
        for bad in (altered, self.fixtures[::-1]):
            with self.assertRaisesRegex(ValueError, "digest"):
                self.make(fixtures=bad)
        with self.assertRaisesRegex(ValueError, "four"):
            self.make(fixtures=self.fixtures[:-1])

    def test_existing_marker_refused(self):
        with self.assertRaisesRegex(ValueError, "marker"):
            self.make(source=self.source + suite.api.MARKER)

    def test_exact_distinct_ignored_test_names(self):
        self.assertEqual(len(set(suite.TESTS)), 4)
        for name, fixture in zip(suite.TESTS, self.fixtures):
            mod, test = name.split("::")
            self.assertIn(("mod " + mod).encode(), fixture)
            self.assertIn(("fn " + test + "(").encode(), fixture)
            self.assertIn(b"#[ignore", fixture)

    def test_wrong_source_cli_does_not_modify_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "xasync.rs"
            output = pathlib.Path(tmp) / "output.rs"
            source.write_bytes(self.source)
            output.write_bytes(b"existing")
            run = subprocess.run([sys.executable, suite.__file__, str(source), str(output)],
                                 capture_output=True, timeout=10)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(source.read_bytes(), self.source)
            self.assertEqual(output.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
