# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify wiring of the ignored queue-only measurement fixture."""
import unittest
from apply_pipeline_perf import PATCHES


class PipelineQueueMeasurementTests(unittest.TestCase):
    def test_actual_queue_measurement_wiring(self):
        patch, = [new for _, new in PATCHES["crates/victory-gpu/src/pipeline/make.rs"]
                  if "mod queue_compaction_measurement" in new]
        fixture = patch.split("mod queue_compaction_measurement", 1)[1]
        self.assertIn("for total in [256usize, 1024, 4096]", fixture)
        self.assertIn("for percent in [25usize, 50, 90]", fixture)
        self.assertIn("for repeat in 0..4", fixture)
        self.assertIn("for prune in [repeat % 2 == 1, repeat % 2 == 0]", fixture)
        self.assertIn("q.pop_with_policy(None, prune)", fixture)
        self.assertIn("Arc::ptr_eq(p, &entries[i])", fixture)
        self.assertIn("assert_eq!(q.early_stale, 0)", fixture)
        self.assertIn("assert_eq!(stale_after_first", fixture)
        self.assertIn("for distributed in [false, true]", fixture)
        self.assertIn("(i + 1) * promoted / total != i * promoted / total", fixture)
        self.assertIn(".chain((0..total).filter(|&i| !is_promoted(i)))", fixture)
        self.assertIn("if repeat != 0", fixture)
        self.assertIn("distributed={} repeat={}", fixture)
        self.assertIn("first_ns={} rest_ns={}", fixture)
        self.assertNotIn(".make()", fixture)
        self.assertNotIn("thread::spawn", fixture)
        self.assertIn('#[ignore = "bounded release-mode synthetic queue measurement"]', fixture)
