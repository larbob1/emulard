# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from frame_report import summarize
from benchmark_pairs import aggregate
from gameplay_acceptance import evaluate
from test_frame_report import sample
from test_gameplay_acceptance import fixture

class LibraryInitTests(unittest.TestCase):
    def test_signed_codes_warmup_and_privacy(self):
        report = summarize(["private-prefix pipeline_library_init_v1 phase=0 hresult=-2147483648",
                            sample(), "pipeline_library_init_v1 phase=1 hresult=0",
                            "pipeline_library_init_v1 phase=1 hresult=2147483647",
                            "pipeline_library_init_v1 phase=2 hresult=-1"], skip=1)
        observed = report["pipeline_library_init"]
        self.assertEqual(observed["message_lines"], 4)
        self.assertEqual(observed["invalid_records"], 0)
        self.assertEqual(observed["phases"]["0"]["latest_hresult"], -2147483648)
        self.assertEqual(observed["phases"]["1"], {"valid_records": 2, "latest_hresult": 2147483647})
        self.assertEqual(observed["phases"]["2"]["latest_hresult"], -1)
        self.assertNotIn("private-prefix", str(report))
        self.assertEqual(summarize([])["pipeline_library_init"]["phases"], {})

    def test_malformed_and_duplicate_markers(self):
        prefix = "pipeline_library_init_v1 "
        bad = ["phase=3 hresult=-1", "phase=1 hresult=-2147483649",
               "phase=1 hresult=2147483648", "phase=1 hresult=0x1",
               "phase=1 hresult=-1 hresult=2", "phase=1", "phase=1 hresult=+1",
               "phase=1 hresult=-1 secret=private-payload",
               "phase=1 hresult=-1 " + prefix + "phase=2 hresult=-2"]
        report = summarize([prefix + s for s in bad] + ["not_pipeline_library_init_v1 phase=1 hresult=-1"])
        observed = report["pipeline_library_init"]
        self.assertEqual(observed["message_lines"], len(bad))
        self.assertEqual(observed["invalid_records"], len(bad))
        self.assertEqual(observed["phases"], {})
        self.assertNotIn("private-payload", str(report))

    def test_pair_separation(self):
        a = summarize([sample(300)])
        b = summarize([sample(150), "pipeline_library_init_v1 phase=1 hresult=-1"])
        row = aggregate([(a,b)])["runs"][0]
        self.assertEqual(row["baseline_pipeline_library_init"]["phases"], {})
        self.assertEqual(row["candidate_pipeline_library_init"]["phases"]["1"]["latest_hresult"], -1)

    def test_acceptance_exclusion(self):
        manifest, lines = fixture()
        for observation in ("pipeline_library_init_v1 phase=1 hresult=-1", "pipeline_library_init_v1 malformed"):
            result = evaluate(manifest, [summarize(lines + [observation])] * 3)
            self.assertEqual(result["milestones"]["30"]["status"], "insufficient_evidence")
            self.assertIn("experimental_library_init_observation_detected", result["runs"][0]["evidence_issues"])
        report = summarize(lines)
        report.pop("pipeline_library_init")
        self.assertEqual(evaluate(manifest, [report] * 3)["milestones"]["30"]["status"], "insufficient_evidence")

if __name__ == "__main__":
    unittest.main()
