# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from frame_report import summarize
from gameplay_acceptance import CHECKS, CONFIG_FIELDS, evaluate
from test_frame_report import sample


def fixture(frame_ms=30, seconds=600, visible=None):
    n = int(seconds * 1000 / frame_ms)
    batch = (f"frame times: {n} frames in {seconds} s: shortest {frame_ms} ms, median {frame_ms}, "
             f"longest {frame_ms}; 0 long (over 100 ms, the usual frame of the last 64 being 20); each: "
             + " ".join([str(frame_ms)] * n))
    config = {key: "private-metadata" for key in CONFIG_FIELDS}
    config["revision"] = "a" * 40
    runs = [{"id": f"private-{i}", "configuration": dict(config),
             "elapsed_seconds": seconds, "correctly_displayed_frames": n if visible is None else visible,
             "checks": dict.fromkeys(CHECKS, True), "log": f"private-{i}.log"} for i in range(3)]
    return {"configuration": config, "runs": runs}, [sample(frame_ms), batch]


class AcceptanceTests(unittest.TestCase):
    def assess(self, manifest, lines):
        return evaluate(manifest, [summarize(lines)] * len(manifest["runs"]))

    def test_complete_evidence_and_privacy(self):
        manifest, lines = fixture()
        result = self.assess(manifest, lines)
        self.assertEqual(result["milestones"]["30"]["status"], "meets_owner_attested_criteria")
        self.assertEqual(result["milestones"]["30"]["qualifying_runs"], 3)
        self.assertFalse(result["independently_verified_gameplay"])
        self.assertNotIn("private-", json.dumps(result))

    def test_visible_rate_not_present_rate(self):
        manifest, lines = fixture(visible=1500)
        result = self.assess(manifest, lines)
        self.assertEqual(result["milestones"]["5"]["status"], "failed")
        self.assertEqual(result["runs"][0]["owner_attested_visible_fps"], 2.5)
        self.assertGreater(result["runs"][0]["approx_present_fps"], 30)

    def test_short_runs_and_repeat_count(self):
        manifest, lines = fixture(seconds=60)
        result = self.assess(manifest, lines)
        self.assertEqual(result["milestones"]["20"]["status"], "meets_owner_attested_criteria")
        self.assertEqual(result["milestones"]["30"]["status"], "failed")
        manifest["runs"].pop()
        self.assertEqual(self.assess(manifest, lines)["milestones"]["20"]["status"], "insufficient_evidence")

    def test_drops_and_correctness_failure(self):
        manifest, lines = fixture()
        manifest["runs"][1]["checks"]["full_scene"] = False
        self.assertEqual(self.assess(manifest, lines)["milestones"]["5"]["status"], "failed")
        manifest["runs"][1]["checks"]["full_scene"] = True
        lines[0] = sample(30, 1)
        self.assertEqual(self.assess(manifest, lines)["milestones"]["30"]["status"], "failed")

    def test_shader_warning_prevents_acceptance_even_with_zero_drop_intervals(self):
        manifest, lines = fixture()
        lines.append("WARN shader does not translate; its pipelines' draws are dropped private-error")
        result = self.assess(manifest, lines)
        self.assertEqual(result["milestones"]["30"]["status"], "insufficient_evidence")
        self.assertEqual(result["runs"][0]["reported_drop_intervals"], 0)
        self.assertEqual(result["runs"][0]["shader_translation_drop_warning_lines"], 1)
        self.assertIn("shader_translation_drop_warning_observed", result["runs"][0]["evidence_issues"])
        self.assertNotIn("private-error", str(result))
        report = summarize(lines[:-1])
        report.pop("shader_translation_drop_warning_lines")
        self.assertEqual(evaluate(manifest, [report] * 3)["milestones"]["30"]["status"], "insufficient_evidence")
        manifest["runs"][0]["checks"]["full_scene"] = False
        self.assertEqual(self.assess(manifest, lines)["milestones"]["30"]["status"], "failed")

    def test_experimental_observation_cannot_certify_performance(self):
        manifest, lines = fixture()
        for observation in ("dirty_observe_v1 path=0 samples=0 bytes=0 chunks=0 unequal=0",
                            "dirty_observe_v1 malformed"):
            result = self.assess(manifest, lines + [observation])
            self.assertEqual(result["milestones"]["30"]["status"], "insufficient_evidence")
            self.assertIn("experimental_dirty_observation_detected", result["runs"][0]["evidence_issues"])
        manifest["runs"][0]["checks"].pop("experimental_observation_disabled")
        self.assertEqual(self.assess(manifest, lines)["milestones"]["30"]["status"], "insufficient_evidence")

    def test_missing_and_inconsistent_evidence(self):
        manifest, lines = fixture()
        self.assertEqual(self.assess(manifest, lines[:1])["milestones"]["30"]["status"], "insufficient_evidence")
        self.assertEqual(self.assess(manifest, lines[1:])["milestones"]["30"]["status"], "insufficient_evidence")
        manifest["runs"][0]["elapsed_seconds"] = 1200
        result = self.assess(manifest, lines)
        self.assertIn("frame_log_duration_not_consistent_with_owner_window", result["runs"][0]["evidence_issues"])
        manifest["runs"][0]["elapsed_seconds"] = 600
        manifest["runs"][0]["correctly_displayed_frames"] = 999999
        self.assertIn("visible_frame_count_exceeds_logged_samples",
                      self.assess(manifest, lines)["runs"][0]["evidence_issues"])

    def test_tail_gate(self):
        manifest, lines = fixture()
        report = summarize(lines)
        report["individual_frame_times"]["frame_ms_percentiles"]["p99"] = 101
        self.assertEqual(evaluate(manifest, [report] * 3)["milestones"]["30"]["status"], "failed")

    def test_metadata_and_duplicate_ids(self):
        manifest, lines = fixture()
        other = copy.deepcopy(manifest)
        other["runs"][0]["configuration"]["platform"] = "different"
        with self.assertRaises(ValueError):
            self.assess(other, lines)
        other = copy.deepcopy(manifest)
        other["runs"][0]["id"] = other["runs"][1]["id"]
        with self.assertRaises(ValueError):
            self.assess(other, lines)

    def test_cli_normalized_log_copies_are_not_independent(self):
        manifest, lines = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            variants = ["\n".join(lines), "\r\n".join(lines) + "\r\n",
                        "\n".join(lines) + "\n"]
            for run, content in zip(manifest["runs"], variants):
                (root / run["log"]).write_bytes(content.encode("utf-8"))
            p = root / "manifest.json"
            p.write_text(json.dumps(manifest), encoding="utf-8")
            proc = subprocess.run([sys.executable,
                                   str(Path(__file__).with_name("gameplay_acceptance.py")),
                                   str(p)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["status"],
                             "invalid_or_unavailable_evidence")
            self.assertNotIn(directory, proc.stdout)

    def test_cli_refuses_log_changed_during_read(self):
        from gameplay_acceptance import main
        manifest, lines = fixture(seconds=1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for run in manifest["runs"]:
                (root / run["log"]).write_text("\n".join(lines), encoding="utf-8")
            p = root / "manifest.json"
            p.write_text(json.dumps(manifest), encoding="utf-8")
            before = SimpleNamespace(st_size=100, st_mtime_ns=1, st_ctime_ns=1)
            after = SimpleNamespace(st_size=101, st_mtime_ns=2, st_ctime_ns=2)
            with patch.object(sys, "argv", ["gameplay_acceptance.py", str(p)]), \
                 patch("benchmark_pairs.os.fstat", side_effect=[before, after]), \
                 patch("builtins.print") as output:
                self.assertEqual(main(), 1)
                self.assertEqual(json.loads(output.call_args.args[0])["status"],
                                 "invalid_or_unavailable_evidence")

    def test_cli_duplicate_content_and_success(self):
        manifest, lines = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for run in manifest["runs"]:
                (root / run["log"]).write_text("\n".join(lines), encoding="utf-8")
            p = root / "private-manifest.json"
            p.write_text(json.dumps(manifest), encoding="utf-8")
            cmd = [sys.executable, str(Path(__file__).with_name("gameplay_acceptance.py")), str(p)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            for i, run in enumerate(manifest["runs"]):
                with (root / run["log"]).open("a", encoding="utf-8") as handle:
                    handle.write(f"\nprivate synthetic run marker {i}\n")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("private-", proc.stdout)
            self.assertEqual(json.loads(proc.stdout)["milestones"]["30"]["status"], "meets_owner_attested_criteria")


if __name__ == "__main__":
    unittest.main()
