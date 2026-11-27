# SPDX-License-Identifier: GPL-3.0-or-later
"""P23 wakeup review, not a proposed runtime change.

Pinned dstorage.rs 51700c6d43a3507fa65e50fe4bb64074ce706cd4
(blob 5fe9aba9aa336dcaace3c21e72040de4efb1e0dd).
work() takes starved and broadcasts on every completion; start() refuses
the selected head if staging is occupied and the next reservation exceeds
the limit. set_staging_buffer_size and close_lane can change eligibility
without notifying work. Submit paths notify all, including empty submits.

This model fixes head order during refusal/mutations, uses explicit
notification events, and does not model OS scheduling, spurious wakes,
the full virtual clocks, real status callbacks, or actual stall duration.
The completing worker can itself start work even without a broadcast.
"""
from dataclasses import dataclass, field
import unittest


@dataclass
class State:
    staged: int
    limit: int
    heads: list = field(default_factory=list)  # ordered (lane, staging bytes)
    starved: bool = False
    work_broadcasts: int = 0
    finished_broadcasts: int = 0

    def eligible(self):
        if not self.heads:
            return False
        _, size = self.heads[0]
        return self.staged == 0 or self.staged + size <= self.limit

    def attempt(self):
        if not self.heads:
            return None
        if not self.eligible():
            self.starved = True
            return None
        lane, size = self.heads.pop(0)
        self.staged += size
        return lane, size

    def resize(self, limit):
        # Existing setter has no work notification.
        self.limit = limit

    def close(self, lane):
        # Remove waiting heads, not running reservations. Model the case
        # where no running request belongs to the closed lane.
        self.heads = [(l, n) for l, n in self.heads if l != lane]
        self.finished_broadcasts += 1

    def submit(self):
        # Even an empty submit currently notifies work.
        self.work_broadcasts += 1

    def finish(self, reservation, *, skip_zero=False):
        assert 0 <= reservation <= self.staged
        self.staged -= reservation
        if self.starved and (not skip_zero or reservation != 0):
            self.starved = False
            self.work_broadcasts += 1
        # Completion waiters are a distinct condition variable.
        self.finished_broadcasts += 1


class StorageWakeupReviewTests(unittest.TestCase):
    def test_zero_release_cannot_change_admission_in_fixed_state(self):
        checked = 0
        for staged in range(9):
            for limit in range(9):
                for next_bytes in range(9):
                    s = State(staged, limit, [(0, next_bytes)])
                    before = s.eligible()
                    s.finish(0, skip_zero=True)
                    self.assertEqual(s.eligible(), before)
                    checked += 1
        self.assertEqual(checked, 729)

    def test_baseline_redundant_wake_under_unchanged_blocked_head(self):
        a = State(60, 100, [(0, 60), (1, 0)])
        b = State(60, 100, [(0, 60), (1, 0)])
        for s in (a, b):
            self.assertIsNone(s.attempt())
        a.finish(0)
        b.finish(0, skip_zero=True)
        self.assertEqual((a.work_broadcasts, b.work_broadcasts), (1, 0))
        self.assertEqual((a.finished_broadcasts, b.finished_broadcasts), (1, 1))
        self.assertFalse(a.eligible())
        self.assertFalse(b.eligible())
        self.assertTrue(b.starved)  # must not consume a pending wake obligation
        b.finish(60, skip_zero=True)
        self.assertEqual(b.work_broadcasts, 1)
        self.assertTrue(b.eligible())

    def test_resize_counterexample_to_unconditional_skip_zero(self):
        for skip in (False, True):
            s = State(60, 100, [(0, 60), (1, 30)])
            self.assertIsNone(s.attempt())
            s.resize(150)
            self.assertTrue(s.eligible())
            self.assertEqual(s.work_broadcasts, 0)
            s.finish(0, skip_zero=skip)
            self.assertEqual(s.work_broadcasts, int(not skip))
            # Finishing worker may claim the first head; another eligible
            # head remains, but sleepers have no explicit wake in skip mode.
            self.assertEqual(s.attempt(), (0, 60))
            self.assertTrue(s.eligible())
            self.assertEqual(s.attempt(), (1, 30))

    def test_close_counterexample_to_unconditional_skip_zero(self):
        for skip in (False, True):
            s = State(60, 100, [(0, 60), (1, 20), (2, 20)])
            self.assertIsNone(s.attempt())
            s.close(0)
            self.assertTrue(s.eligible())
            self.assertEqual(s.work_broadcasts, 0)
            s.finish(0, skip_zero=skip)
            self.assertEqual(s.work_broadcasts, int(not skip))
            self.assertEqual(s.attempt(), (1, 20))
            self.assertTrue(s.eligible())
            self.assertEqual(s.attempt(), (2, 20))

    def test_empty_submit_can_wake_after_unnotified_limit_change(self):
        s = State(60, 100, [(0, 60)])
        self.assertIsNone(s.attempt())
        s.resize(120)
        self.assertTrue(s.eligible())
        self.assertEqual(s.work_broadcasts, 0)
        s.submit()
        self.assertEqual(s.work_broadcasts, 1)

    def test_positive_release_preserves_oversized_alone_rule(self):
        for skip in (False, True):
            s = State(60, 100, [(0, 500), (1, 0)])
            self.assertIsNone(s.attempt())
            s.finish(60, skip_zero=skip)
            self.assertEqual(s.work_broadcasts, 1)
            self.assertEqual(s.attempt(), (0, 500))
            self.assertIsNone(s.attempt())
            s.finish(500, skip_zero=skip)
            self.assertEqual(s.attempt(), (1, 0))

    def test_exhaustive_resize_and_close_counterexamples_exist(self):
        resize_cases = close_cases = 0
        for staged in range(1, 5):
            for limit in range(5):
                for head in range(5):
                    for other in range(5):
                        for new_limit in range(9):
                            a = State(staged, limit, [(0, head), (1, other)])
                            if a.eligible():
                                continue
                            a.attempt()
                            a.resize(new_limit)
                            if a.eligible():
                                a.finish(0, skip_zero=True)
                                self.assertTrue(a.starved)
                                self.assertEqual(a.work_broadcasts, 0)
                                resize_cases += 1
                        b = State(staged, limit, [(0, head), (1, other)])
                        if b.eligible():
                            continue
                        b.attempt()
                        b.close(0)
                        if b.eligible():
                            b.finish(0, skip_zero=True)
                            self.assertEqual(b.work_broadcasts, 0)
                            close_cases += 1
        self.assertGreater(resize_cases, 0)
        self.assertGreater(close_cases, 0)


if __name__ == "__main__":
    unittest.main()
