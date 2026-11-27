# SPDX-License-Identifier: GPL-3.0-or-later
import json
import unittest
from readiness_report import summarize_readiness

class ReadinessReportTests(unittest.TestCase):
    def test_only_known_labels_and_counts_escape(self):
        lines = [
            "private-path hash=deadbeef shader does not translate; its pipelines' draws are dropped error=a wave reduction where not every lane runs",
            "shader does not translate; its pipelines' draws are dropped error=private-reason",
            "the ray-tracing structure builder stays off: not all of its programs have a host pipeline missing=3 of=52",
            "shaders touched pages that had no copy pages=9 first=0xabcdef",
            "completed raw memory feedback missing=2 dirty_pages=4",
        ]
        report = summarize_readiness(iter(lines))
        self.assertEqual(report["translation_warning_counts"]["wave_control_flow"], 1)
        self.assertEqual(report["translation_warning_counts"]["other"], 1)
        self.assertEqual(report["builder"]["last_missing"], 3)
        self.assertEqual(report["builder"]["last_total"], 52)
        self.assertEqual(report["memory"]["reported_missing_pages"], 9)
        self.assertEqual(report["memory"]["reported_dirty_pages"], 4)
        out = json.dumps(report)
        for secret in ("private-path", "deadbeef", "private-reason", "abcdef"):
            self.assertNotIn(secret, out)

    def test_builder_success_does_not_hide_later_failure(self):
        report = summarize_readiness([
            "the ray-tracing structure builder runs: all of its programs have host pipelines pipelines=52",
            "the ray-tracing structure builder is turned off for the rest of the run",
        ])
        self.assertEqual(report["builder"]["ready_reports"], 1)
        self.assertEqual(report["builder"]["disabled_reports"], 1)

    def test_empty_log_has_no_inferred_success(self):
        report = summarize_readiness([])
        self.assertIsNone(report["builder"]["last_missing"])
        self.assertEqual(report["frame"]["samples"], 0)

if __name__ == "__main__":
    unittest.main()
