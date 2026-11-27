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
        self.assertEqual(report["builder"]["latest_observed_state"], "disabled_unconditional")
        self.assertEqual(report["builder"]["last_numeric_quality"], "not_applicable")
        self.assertIsNone(report["builder"]["last_missing"])
        self.assertIsNone(report["builder"]["last_total"])

    def test_builder_numeric_quality_and_no_stale_counts(self):
        ready = "the ray-tracing structure builder runs: all of its programs have host pipelines"
        disabled = "the ray-tracing structure builder stays off:"
        for fields, quality in [
            ("missing=3 of=2", "invalid"), ("missing=0 of=2", "invalid"),
            ("missing=3 of=52 missing=bad", "invalid"),
            ("missing=3", "missing"), ("missing=3 of=52.5", "invalid"),
        ]:
            report = summarize_readiness([ready + " pipelines=52", disabled + " " + fields])
            builder = report["builder"]
            self.assertEqual(builder["latest_observed_state"], "disabled_missing_pipelines")
            self.assertEqual(builder["last_numeric_quality"], quality)
            self.assertEqual(builder["unusable_numeric_reports"], 1)
            self.assertIsNone(builder["last_missing"])
            self.assertIsNone(builder["last_total"])
        for fields in ("pipelines=52 pipelines=bad", "pipelines=52.5", "pipelines=52x"):
            builder = summarize_readiness([ready + " " + fields])["builder"]
            self.assertEqual(builder["last_numeric_quality"], "invalid")
            self.assertIsNone(builder["last_missing"])
            self.assertIsNone(builder["last_total"])

    def test_builder_fields_before_message(self):
        report = summarize_readiness([
            "missing=3 of=52 the ray-tracing structure builder stays off: not all of its programs have a host pipeline"
        ])
        self.assertEqual(report["builder"]["last_missing"], 3)
        self.assertEqual(report["builder"]["last_total"], 52)
        self.assertEqual(report["builder"]["last_numeric_quality"], "valid")

    def test_empty_log_has_no_inferred_success(self):
        report = summarize_readiness([])
        self.assertIsNone(report["builder"]["last_missing"])
        self.assertEqual(report["builder"]["latest_observed_state"], "unobserved")
        self.assertEqual(report["builder"]["last_numeric_quality"], "unobserved")
        self.assertEqual(report["frame"]["samples"], 0)

if __name__ == "__main__":
    unittest.main()
