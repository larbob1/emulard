import os
import tempfile
import unittest

from clock_preflight_report import report, read_rows


def row(seq, kind, *, start=None, end=None, outcome=0, fields=None):
    schedule = seq * 1000
    start = schedule + 10 if start is None else start
    end = start + 20 if end is None else end
    if fields is None:
        fields = ["RssAnon"] if kind == "status" else ["MemAvailable"]
    return dict(sequence=seq, scheduled_relative_ns=schedule,
                read_start_relative_ns=start, read_end_relative_ns=end,
                outcome_code=outcome, available_fields=fields,
                values_bytes={field: 100 for field in fields})


class ClockPreflightTests(unittest.TestCase):
    def test_pending_read_and_independent_guard(self):
        status = [row(0, "status"), row(1, "status", start=1010, end=2000,
                                       outcome=1, fields=[])]
        guard = [row(0, "guard"), row(1, "guard")]
        guard[-1].update(stop_before_relative_ns=1040, stop_after_relative_ns=1045)
        result = report(status, guard, 2, 1000, True)
        self.assertEqual(result["status"]["valid_read_cost"]["max_ns"], 20)
        self.assertEqual(result["status"]["outcomes"]["unavailable"], 1)
        self.assertEqual(result["guard"]["stop_dispatch_ns"], 5)
        self.assertEqual(result["status_read_spans_stop_dispatch_count"], 1)
        self.assertIsNone(report(status, guard, 2, 1000)
                          ["status_read_spans_stop_dispatch_count"])

    def test_missing_sequence_and_partial_fields(self):
        result = report([row(0, "status"), row(2, "status")], [], 3, 1000)
        self.assertEqual(result["status"]["unobserved_sequence_slots"], 1)
        self.assertEqual(result["guard"]["unobserved_sequence_slots"], 3)
        self.assertEqual(result["status"]["valid_field_coverage"]["RssAnon"], 2)
        self.assertEqual(result["status"]["valid_field_coverage"]["RssFile"], 0)
        self.assertIsNone(result["guard"]["valid_read_cost"]["max_ns"])

    def test_duplicate_reverse_and_bad_fields(self):
        a = row(0, "status")
        bad = row(1, "status")
        bad["available_fields"] = ["RssAnon", "RssAnon"]
        private = row(1, "status", fields=["private_path"])
        result = report([a, a, bad, private], [], 2, 1000)
        self.assertEqual(result["status"]["malformed_or_out_of_order_rows"], 3)
        self.assertEqual(result["status"]["accepted_rows"], 1)
        self.assertNotIn("private_path", str(result))

    def test_cadence_and_stop_bounds(self):
        a, b = row(0, "guard"), row(1, "guard")
        b["scheduled_relative_ns"] = 999
        result = report([], [a, b], 2, 1000)
        self.assertEqual(result["guard"]["cadence_errors"], 1)
        b.update(stop_before_relative_ns=0, stop_after_relative_ns=10)
        result = report([], [a, b], 2, 1000)
        self.assertEqual(result["guard"]["malformed_or_out_of_order_rows"], 1)
        self.assertFalse(result["guard"]["stop_observed"])

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sample.jsonl")
            with open(path, "w", encoding="utf-8") as target:
                target.write('{"sequence":0,"sequence":1}\n')
            with self.assertRaises(ValueError):
                list(read_rows(path))


if __name__ == "__main__":
    unittest.main()
