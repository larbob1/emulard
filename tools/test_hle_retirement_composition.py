import unittest
import apply_hle_pool_native as install
import test_hle_idle_suite_preview as retirement
import preview_hle_pool_native as baseline

class RetirementCompositionTests(unittest.TestCase):
    def test_independent_prefixes_and_markers(self):
        idle = retirement.idle
        source = idle.STRUCT + b"\n\n" + idle.STATIC + b"\n\n" + idle.IMPL
        expected = baseline.git_blob(source)
        reentrant = baseline.FIXTURE.read_bytes()
        fixtures = retirement.fixtures()
        result = install.compose(source, reentrant, fixtures, expected)
        first = baseline.preview(source, reentrant, expected)
        second = retirement.preview(source, fixtures, expected)
        self.assertEqual(result, first + b"\n" + second[len(source)+1:])
        self.assertEqual(result.count(b"#[ignore ="), 6)
        with self.assertRaises(ValueError):
            install.compose(source, reentrant + b"\n", fixtures, expected)
        with self.assertRaises(ValueError):
            install.compose(source, reentrant, fixtures)
