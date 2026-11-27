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

    def test_config_and_zero_denominator(self):
        duplicate = summarize_storage(configuration() * 2 + [window()])
        self.assertFalse(duplicate["worker_configuration_verified"])
        zero = summarize_storage(configuration() + [window(rate=0)])
        good = summarize_storage(configuration(2) + [window(rate=20)])
        self.assertIsNone(compare_storage(zero, good)["destination_rate_ratio"])
        self.assertEqual(compare_storage(good, good)["destination_rate_ratio"], 1)
        self.assertEqual(compare_storage(zero, good)["destination_rate_delta"], 20)

    def test_cli_numeric_output_no_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = (Path(directory) / name for name in ("private-a.log", "private-b.log"))
            for p in (a, b):
                p.write_text("\n".join(configuration() + [window()]), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("storage_report.py")),
                                   str(b), "--baseline", str(a), "--skip", "0"],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["comparison"]["comparison_usable"])
            self.assertNotIn(directory, proc.stdout)


if __name__ == "__main__":
    unittest.main()
