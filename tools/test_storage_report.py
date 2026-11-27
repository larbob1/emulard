# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from storage_report import compare_storage, summarize_storage


def configuration(workers=4, automatic=16):
    return [f"private dstorage: worker configuration workers={workers} default={automatic}",
            f"private dstorage: workers workers={workers}"]


def window(seconds=5, rate=20, waiting=3):
    return (f"private dstorage: last {seconds} s requests=10 mb_per_s={rate} "
            f"busy_workers=3.0 reading_workers=1.0 staging_waits=2 bcpack_mb=4 "
            f"bcpack_workers=0.5 waiting={waiting}")


class StorageReportTests(unittest.TestCase):
    def test_elapsed_weighted_rate(self):
        report = summarize_storage(configuration() + [window(5, 20), window(10, 50, 7)])
        self.assertTrue(report["worker_configuration_verified"])
        self.assertEqual(report["finished_requests"], 20)
        self.assertEqual(report["weighted_destination_mb_per_s"], 40)
        self.assertEqual(report["approx_destination_mb"], 600)
        self.assertEqual(report["waiting_snapshot_max"], 7)
        self.assertEqual(report["staging_waits"], 4)
        self.assertNotIn("private", str(report))

    def test_missing_malformed_and_warmup(self):
        result = summarize_storage(configuration() + [window(), window(0), window().replace("waiting=3", "waiting=bad"),
                                                        window(5, 30)], skip=1)
        self.assertEqual(result["windows_invalid_after_warmup"], 2)
        self.assertEqual(result["windows_skipped"], 1)
        self.assertEqual(result["weighted_destination_mb_per_s"], 30)
        self.assertFalse(compare_storage(result, result)["comparison_usable"])
        empty = summarize_storage([])
        self.assertIsNone(empty["finished_requests"])
        self.assertIsNone(empty["weighted_destination_mb_per_s"])
        self.assertFalse(compare_storage(empty, result)["comparison_usable"])

    def test_ambiguous_assignments_and_window_markers(self):
        good = window()
        bad = [good + " waiting=bad", good + " waiting=",
               good + " mb_per_s=1", good + " dstorage: last malformed",
               good.replace("waiting=3", "waiting=3x"),
               good.replace("mb_per_s=20", "mb_per_s=20.0.0")]
        result = summarize_storage(configuration() + bad + [good])
        self.assertEqual(result["windows_invalid_after_warmup"], len(bad))
        self.assertEqual(result["windows_used"], 1)
        self.assertFalse(compare_storage(result, result)["comparison_usable"])
        malformed_config = configuration()
        malformed_config[0] += " workers=bad"
        self.assertFalse(summarize_storage(malformed_config + [good])
                         ["worker_configuration_verified"])

    def test_numeric_limits_refuse_without_losing_valid_rows(self):
        good = window()
        bad = [good.replace("requests=10", "requests=" + str(2**64)),
               good.replace("requests=10", "requests=" + "9" * 5000),
               good.replace("mb_per_s=20", "mb_per_s=" + "9" * 400),
               window(seconds="9" * 400),
               window(seconds="0.0000000001")]
        result = summarize_storage(configuration() + bad + [good])
        self.assertEqual(result["windows_invalid_after_warmup"], len(bad))
        self.assertEqual(result["windows_used"], 1)
        self.assertEqual(result["weighted_destination_mb_per_s"], 20)
        json.dumps(result, allow_nan=False)

    def test_config_and_zero_denominator(self):
        duplicate = summarize_storage(configuration() * 2 + [window()])
        self.assertFalse(duplicate["worker_configuration_verified"])
        zero = summarize_storage(configuration() + [window(rate=0)])
        good = summarize_storage(configuration(2) + [window(rate=20)])
        self.assertIsNone(compare_storage(zero, good)["destination_rate_ratio"])
        self.assertEqual(compare_storage(good, good)["destination_rate_ratio"], 1)
        self.assertEqual(compare_storage(zero, good)["destination_rate_delta"], 20)

    def test_physical_destination_evidence_and_failure(self):
        prefix = "private-offset dstorage: "
        retry = prefix + "a destination's physical pages written after a retry"
        exhausted = prefix + "retries used up (VICTORY_DSTORAGE_RETRIES)"
        failed = prefix + "a destination's physical pages could not be written (unknown page or a host failure); its request fails"
        queue = prefix + "a queue half full submitted itself; reads into physical pages wait for the title's Submit"
        clean = summarize_storage(configuration() + [window()])
        self.assertFalse(clean["physical_destination_attempt_evidence"])
        queued = summarize_storage(configuration() + [queue, window()])
        self.assertFalse(queued["physical_destination_attempt_evidence"])
        self.assertEqual(queued["physical_destination_observations"]["half_full_queue_lines"], 1)
        good = summarize_storage(configuration() + [window(), retry, window()], skip=1)
        self.assertTrue(good["physical_destination_attempt_evidence"])
        self.assertFalse(good["storage_page_lookup_execution_verified"])
        self.assertTrue(compare_storage(clean, good)["comparison_usable"])
        bad = summarize_storage(configuration() + [exhausted, failed, window(), window()], skip=1)
        self.assertTrue(bad["physical_destination_failure_observed"])
        self.assertEqual(bad["physical_destination_observations"]["retry_exhausted_lines"], 1)
        self.assertEqual(bad["physical_destination_observations"]["physical_write_failure_lines"], 1)
        self.assertFalse(compare_storage(clean, bad)["comparison_usable"])
        self.assertIsNone(compare_storage(clean, bad)["destination_rate_ratio"])
        self.assertNotIn("private-offset", str(bad))

    def test_no_finished_requests_is_not_comparison_evidence(self):
        empty = summarize_storage(configuration() + [window().replace("requests=10", "requests=0")])
        self.assertEqual(empty["finished_requests"], 0)
        self.assertFalse(compare_storage(empty, empty)["comparison_usable"])

    def test_cli_rejects_copied_normalized_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = (Path(directory) / name for name in ("private-a.log", "private-b.log"))
            lines = configuration() + [window()]
            a.write_bytes(("\n".join(lines) + "\n").encode())
            b.write_bytes("\r\n".join(lines).encode())
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("storage_report.py")),
                                   str(b), "--baseline", str(a), "--skip", "0"],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["reason"], "repeated_log_content")
            self.assertNotIn(directory, proc.stdout)

    def test_cli_numeric_output_no_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = (Path(directory) / name for name in ("private-a.log", "private-b.log"))
            a.write_text("\n".join(configuration() + [window()]), encoding="utf-8")
            b.write_text("\n".join(configuration() + [window(rate=30)]), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("storage_report.py")),
                                   str(b), "--baseline", str(a), "--skip", "0"],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["comparison"]["comparison_usable"])
            self.assertNotIn(directory, proc.stdout)


if __name__ == "__main__":
    unittest.main()
