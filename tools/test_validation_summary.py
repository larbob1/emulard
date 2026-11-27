# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from ci_compile import validation_summary

class ValidationSummaryTests(unittest.TestCase):
    def test_reports_each_mode_without_raw_output(self):
        lines = [
            b"Running runtime test: victory-hle physical_pages_map_alias_and_unmap\n",
            b"Runtime test switches: VICTORY_MAP_DIFF=0\n",
            b"private raw source\n",
            b"Runtime validation passed: victory-hle physical_pages_map_alias_and_unmap\n",
            b"Running runtime test: victory-hle physical_pages_map_alias_and_unmap\n",
            b"Runtime test switches: VICTORY_MAP_DIFF=1\n",
            b"Runtime validation failed: victory-hle physical_pages_map_alias_and_unmap\n",
            b"Runtime validation passed: release build\n",
        ]
        self.assertEqual(validation_summary(lines), [
            "passed: victory-hle physical_pages_map_alias_and_unmap [VICTORY_MAP_DIFF=0]",
            "failed: victory-hle physical_pages_map_alias_and_unmap [VICTORY_MAP_DIFF=1]",
            "passed: release build",
        ])

    def test_counts_only_for_matching_successful_suite(self):
        lines = [
            b"Running runtime test: victory-gpu cpu_trace\n",
            b"Runtime test counts: victory-gpu cpu_trace passed=30 failed=0\n",
            b"Runtime validation passed: victory-gpu cpu_trace\n",
            b"Running runtime test: victory-gpu window_tests\n",
            b"Runtime test counts: victory-gpu cpu_trace passed=30 failed=0\n",
            b"Runtime validation passed: victory-gpu window_tests\n",
            b"Running runtime test: victory-gpu cpu_trace\n",
            b"Runtime test counts: victory-gpu cpu_trace passed=30 failed=0\n",
            b"Runtime validation failed: victory-gpu cpu_trace\n",
            b"Runtime validation passed: diagnostics build\n",
        ]
        self.assertEqual(validation_summary(lines), [
            "passed: victory-gpu cpu_trace [passed=30 failed=0]",
            "passed: victory-gpu window_tests",
            "failed: victory-gpu cpu_trace",
            "passed: diagnostics build",
        ])

    def test_completion_counts_associate_with_each_mode(self):
        label = b"victory-gpu actual_pending_refusal_notifies_waiters"
        lines = []
        for mode in (b"0", b"1"):
            lines.extend([
                b"Running runtime test: " + label + b"\n",
                b"Runtime test switches: VICTORY_PIPELINE_COMPLETION_STRIPES=" + mode + b"\n",
                b"Runtime test counts: " + label + b" passed=1 failed=0\n",
                b"Runtime validation passed: " + label + b"\n",
            ])
        self.assertEqual(validation_summary(lines), [
            "passed: victory-gpu actual_pending_refusal_notifies_waiters [VICTORY_PIPELINE_COMPLETION_STRIPES=0] [passed=1 failed=0]",
            "passed: victory-gpu actual_pending_refusal_notifies_waiters [VICTORY_PIPELINE_COMPLETION_STRIPES=1] [passed=1 failed=0]",
        ])

    def test_qualified_hle_suite_exact_count(self):
        label = b"victory-hle hle_pool_native_review::reentrant_pool_callback_progress"
        self.assertEqual(validation_summary([
            b"Running runtime test: " + label + b"\n",
            b"Runtime test counts: " + label + b" passed=1 failed=0\n",
            b"Runtime validation passed: " + label + b"\n",
        ]), ["passed: victory-hle hle_pool_native_review::reentrant_pool_callback_progress [passed=1 failed=0]"])

    def test_separate_codec_counts(self):
        lines = []
        for name in (b"victory-hle storage_codec_native_chain_address", b"victory-hle storage_codec_native_chain_pages", b"victory-hle storage_codec_native_partial_error"):
            lines.extend([b"Running runtime test: " + name + b"\n",
                          b"Runtime test counts: " + name + b" passed=1 failed=0\n",
                          b"Runtime validation passed: " + name + b"\n"])
        self.assertEqual(validation_summary(lines), [
            "passed: victory-hle storage_codec_native_chain_address [passed=1 failed=0]",
            "passed: victory-hle storage_codec_native_chain_pages [passed=1 failed=0]",
            "passed: victory-hle storage_codec_native_partial_error [passed=1 failed=0]",
        ])

if __name__ == "__main__":
    unittest.main()
