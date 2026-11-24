# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from frame_report import summarize

def sample(frame=250, dropped=0):
    return (f"synthetic-prefix 4.0 fps, {frame} ms/frame "
            "(80.0 preparing: copies 20.0 ms 8.0 MB, textures 10.0 ms 4.0 MB; "
            f"120.0 on the GPU; 20.0 copying back 2.0 MB), 100 draws/frame, "
            f"dropped {dropped} without a host pipeline (0 being made)")

class FrameReportTests(unittest.TestCase):
    def test_frame_budget(self):
        report = summarize([sample(250), sample(100)])
        self.assertEqual(report["samples"], 2)
        self.assertEqual(report["median_reported_interval"]["frame"], 175)
        self.assertEqual(report["frame_ms_above_target"], 75)
        self.assertEqual(report["intervals_at_or_below_target"], 1)

    def test_dropped_draws_not_hidden(self):
        self.assertEqual(summarize([sample(100, 10)])["intervals_with_dropped_draws"], 1)

    def test_skip_and_ignore_unknown(self):
        self.assertEqual(summarize([sample(), "unknown", sample(100)], 1)["samples"], 1)

    def test_empty_and_zero(self):
        self.assertEqual(summarize(["unknown", sample(0)])["samples"], 0)

    def test_prefix_not_exported(self):
        self.assertNotIn("synthetic-prefix", str(summarize([sample()])))

if __name__ == "__main__":
    unittest.main()
