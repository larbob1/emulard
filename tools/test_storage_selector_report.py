# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from storage_selector_report import expected_keys, summarize


def fixture():
    rows = []
    # Independent occupancy and elapsed values, known 20% lower on path.
    for n in (1, 8, 32, 64, 256):
        for label, busy in (("empty", 0), ("sparse", len(range(0, n, 8))),
                            ("dense", sum(i % 4 != 3 for i in range(n)))):
            for repeat in range(5):
                for mode in (repeat % 2, 1 - repeat % 2):
                    selected = 2000 if busy else 0
                    elapsed = (10000 + 1000 * repeat) * (4 if mode else 5)
                    rows.append(
                        f"storage_selector_timing lanes={n} occupancy={label}"
                        f" nonempty={busy} repeat={repeat} mode={mode}"
                        f" warmup=256 attempts=2000 selected={selected}"
                        f" empty={2000-selected} elapsed_ns={elapsed}")
    return rows


class StorageSelectorReportTests(unittest.TestCase):
    def test_complete_pairs(self):
        result = summarize(fixture())
        self.assertTrue(result["valid"])
        self.assertFalse(result["provenance_verified"])
        self.assertEqual(result["valid_rows"], 150)
        self.assertEqual(len(result["cases"]), 15)
        for case in result["cases"]:
            self.assertEqual(case["paired_on_over_off"]["median"], 0.8)
            self.assertEqual(case["paired_difference_ns_per_attempt"]["median"], -6)
            self.assertEqual([x["pair_count"] for x in case["by_first_mode"]], [3, 2])

    def test_missing_duplicate_and_reordered(self):
        rows = fixture()
        for changed in (rows[:-1], rows + rows[:1],
                        [rows[1], rows[0]] + rows[2:]):
            with self.subTest(length=len(changed)):
                result = summarize(changed)
                self.assertFalse(result["valid"])
                self.assertEqual(result["cases"], [])

    def test_invalid_counts(self):
        for old, new in (("nonempty=0", "nonempty=1"),
                         ("warmup=256", "warmup=255"),
                         ("attempts=2000", "attempts=1999"),
                         ("selected=0", "selected=1"),
                         ("empty=2000", "empty=1999")):
            rows = fixture()
            rows[0] = rows[0].replace(old, new)
            result = summarize(rows)
            self.assertFalse(result["valid"])
            self.assertEqual(result["errors"]["invalid_counts"], 1)

    def test_invalid_timing(self):
        for token in ("0", str(2**128), "-1", "NaN", "1e3"):
            rows = fixture()
            rows[0] = rows[0].rsplit("=", 1)[0] + "=" + token
            result = summarize(rows)
            self.assertFalse(result["valid"])
            self.assertEqual(result["cases"], [])

    def test_unexpected_and_private_text(self):
        rows = fixture()
        rows[0] = rows[0].replace("lanes=1 ", "lanes=2 ")
        result = summarize(rows + ["private payload"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"]["unexpected"], 1)
        self.assertEqual(result["errors"]["malformed"], 1)
        self.assertNotIn("private payload", str(result))

    def test_exact_shape(self):
        self.assertEqual(len(set(expected_keys())), 150)
        self.assertFalse(summarize([])["valid"])
        rows = fixture()
        self.assertFalse(summarize([rows[0] + " mode=1"] + rows[1:])["valid"])


if __name__ == "__main__":
    unittest.main()
