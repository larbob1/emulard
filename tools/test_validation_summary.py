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
        label = b"victory-hle mapping_diagnostic_actual_views"
        lines = []
        for mode in (b"0", b"1"):
            lines.extend([
                b"Running runtime test: " + label + b"\n",
                b"Runtime test switches: VICTORY_MAPPING_DIAGNOSTIC=" + mode + b"\n",
                b"Runtime test counts: " + label + b" passed=1 failed=0\n",
                b"Runtime validation passed: " + label + b"\n",
            ])
        self.assertEqual(validation_summary(lines), [
            "passed: victory-hle mapping_diagnostic_actual_views [VICTORY_MAPPING_DIAGNOSTIC=0] [passed=1 failed=0]",
            "passed: victory-hle mapping_diagnostic_actual_views [VICTORY_MAPPING_DIAGNOSTIC=1] [passed=1 failed=0]",
        ])

    def test_reverse_anomaly_mode_proofs(self):
        lines, expected = [], []
        for name in ("mapping_diagnostic_missing_reverse_key", "mapping_diagnostic_missing_reverse_address", "mapping_diagnostic_duplicate_reverse_address"):
            label = ("victory-hle " + name).encode("ascii")
            for mode in (b"0", b"1"):
                lines.extend([b"Running runtime test: " + label + b"\n",
                              b"Runtime test switches: VICTORY_MAPPING_DIAGNOSTIC=" + mode + b"\n",
                              b"Runtime test counts: " + label + b" passed=1 failed=0\n",
                              b"Runtime validation passed: " + label + b"\n"])
                expected.append("passed: victory-hle " + name + " [VICTORY_MAPPING_DIAGNOSTIC=" + mode.decode() + "] [passed=1 failed=0]")
        self.assertEqual(validation_summary(lines), expected)

if __name__ == "__main__":
    unittest.main()
