# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import tempfile
import unittest

from host_profile import summarize
from host_pressure_report import load_report, summarize_tail


def row(available, rss, file_rss, dt=1):
    return {"elapsed_seconds": dt, "cpu_seconds": 0,
            "cpu_core_equivalents": 0, "rss_end_bytes": rss,
            "memory_end": {"system_available_bytes": available,
                           "process_file_rss_bytes": file_rss,
                           "process_status_rss_bytes": rss},
            "read_bytes": 0, "write_bytes": 0,
            "stable_thread_metrics_available": False,
            "snapshot_read_seconds_max": 0.01,
            "private": "never export"}


class PressureReportTests(unittest.TestCase):
    def test_actual_producer_and_tail_elapsed(self):
        rows = [row(900, 100, 0, 2), row(800, 200, 10),
                row(700, 300, None), row(500, 400, 100, 2),
                row(300, 600, 200), row(100, 900, 450)]
        result = summarize_tail(summarize(rows, 8, "process_unavailable"), 3)
        self.assertFalse(result["source_complete"])
        tail = result["tail_endpoints"]
        self.assertEqual([x["interval"] for x in tail], [4, 5, 6])
        self.assertEqual([x["relative_end_seconds"] for x in tail], [6, 7, 8])
        self.assertIsNone(tail[0]["adjacent_endpoint_delta_bytes"])
        delta = tail[-1]["adjacent_endpoint_delta_bytes"]
        self.assertEqual(delta["system_available_bytes"], -200)
        self.assertEqual(delta["process_file_rss_bytes"], 250)
        self.assertNotIn("read_bytes", delta)
        self.assertNotIn("never export", json.dumps(result))
        self.assertNotIn("process_unavailable", json.dumps(result))

    def test_gaps_zero_and_invalid_not_bridged(self):
        rows = [row(10, 1, 0), row(8, 2, None),
                row(5, 3, 2), row(0, 4, True)]
        report = {"intervals": rows, "requested_intervals": 5,
                  "completed_intervals": 4, "complete": False}
        result = summarize_tail(report)
        tail = result["tail_endpoints"]
        self.assertEqual(tail[0]["values"]["process_file_rss_bytes"], 0)
        for entry in tail[1:]:
            self.assertIsNone(entry["adjacent_endpoint_delta_bytes"]
                              ["process_file_rss_bytes"])
        self.assertEqual(result["tail_field_coverage"]["process_file_rss_bytes"],
                         {"valid": 2, "missing": 1, "invalid": 1})
        self.assertEqual(tail[-1]["values"]["system_available_bytes"], 0)

    def test_invalid_population_and_time(self):
        base = {"intervals": [row(1, 1, 1)], "requested_intervals": 1,
                "completed_intervals": 1, "complete": True}
        for updates in ({"completed_intervals": 0}, {"complete": "yes"},
                        {"requested_intervals": True},
                        {"intervals": [row(1, 1, 1, float("inf"))]},
                        {"intervals": [row(1, 1, 1, 0)]}):
            with self.assertRaises(ValueError):
                summarize_tail(dict(base, **updates))

    def test_duplicate_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            for payload in ('{"x": 1, "x": 2}', '{"x": NaN}'):
                path.write_text(payload)
                with self.assertRaises(ValueError):
                    load_report(path)

    def test_empty_and_malformed_memory(self):
        empty = summarize_tail({"intervals": [], "requested_intervals": 1,
                                "completed_intervals": 0, "complete": False})
        self.assertEqual(empty["tail_endpoints"], [])
        bad = row(0, 1, 0)
        bad["memory_end"] = "secret payload"
        result = summarize_tail({"intervals": [bad], "requested_intervals": 1,
                                 "completed_intervals": 1, "complete": True})
        self.assertEqual(result["tail_field_coverage"]["system_available_bytes"]
                         ["invalid"], 1)
        self.assertNotIn("secret payload", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
