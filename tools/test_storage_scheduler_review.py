# SPDX-License-Identifier: GPL-3.0-or-later
"""P23 review-only model for dstorage::Lanes::start; no runtime registration.

Pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4, prepared
on 6b19a42d6f0d95fe8ec42ef4a6f056a0ad96414b with the existing worker cap.
The proposed Rust hunk is a preview, not an applied or compiled patch.
"""
from dataclasses import dataclass
import random
import unittest

OLD = """        let busy = || self.lanes.iter().filter(|(_, l)| !l.reads.is_empty());
        let (_, class) = busy().map(|(_, l)| (self.clock[l.class], l.class)).min()?;
        let (_, _, id) = busy()
            .filter(|(_, l)| l.class == class)
            .filter_map(|(&id, l)| Some((l.clock, l.reads.front()?.0, id)))
            .min()?;"""
NEW = """        let (_, class, _, _, id) = self.lanes.iter()
            .filter_map(|(&id, l)| {
                let seq = l.reads.front()?.0;
                Some((self.clock[l.class], l.class, l.clock, seq, id))
            })
            .min()?;"""


def preview(source):
    if source.count(OLD) != 1:
        raise ValueError("expected one exact Lanes::start selection anchor")
    return source.replace(OLD, NEW, 1)


@dataclass(frozen=True)
class Lane:
    id: int
    cls: int
    clock: int
    seq: int | None  # None means no submitted reads
    staging: int = 0


def two_pass(lanes, clocks):
    classes = [(clocks[l.cls], l.cls) for l in lanes if l.seq is not None]
    if not classes:
        return None
    _, cls = min(classes)
    return min((l.clock, l.seq, l.id) for l in lanes
               if l.seq is not None and l.cls == cls)[2]


def one_pass(lanes, clocks):
    keys = ((clocks[l.cls], l.cls, l.clock, l.seq, l.id)
            for l in lanes if l.seq is not None)
    best = min(keys, default=None)
    return None if best is None else best[-1]


def admitted(select, lanes, clocks, staged, limit):
    selected = select(lanes, clocks)
    if selected is None:
        return None, False
    lane = next(l for l in lanes if l.id == selected)
    # Preserve the current head-of-line refusal, even if another lane fits.
    if staged > 0 and staged + lane.staging > limit:
        return None, True
    return selected, False


class StorageSchedulerReviewTests(unittest.TestCase):
    def test_exact_anchor_and_drift(self):
        self.assertEqual(preview("before\n" + OLD + "\nafter"),
                         "before\n" + NEW + "\nafter")
        for source in ("", OLD + "\n" + OLD, OLD.replace(".min()?", ".max()?", 1)):
            with self.assertRaises(ValueError):
                preview(source)

    def test_no_submitted_reads(self):
        for lanes in ([], [Lane(1, 2, 0, None)]):
            self.assertIsNone(two_pass(lanes, [0, 0, 0]))
            self.assertIsNone(one_pass(lanes, [0, 0, 0]))

    def test_class_then_lane_then_sequence_then_id(self):
        lanes = [Lane(8, 1, 0, 0), Lane(9, 0, 8, 1),
                 Lane(7, 0, 2, 4), Lane(4, 0, 2, 3), Lane(3, 0, 2, 3)]
        self.assertEqual(two_pass(lanes, [5, 5, 0]), 3)
        self.assertEqual(one_pass(lanes, [5, 5, 0]), 3)
        self.assertEqual(one_pass(lanes, [5, 4, 0]), 8)

    def test_refusal_and_oversized_alone(self):
        lanes = [Lane(1, 0, 0, 1, 64), Lane(2, 1, 0, 2, 0)]
        for select in (two_pass, one_pass):
            self.assertEqual(admitted(select, lanes, [0, 0, 0], 1, 32), (None, True))
            self.assertEqual(admitted(select, lanes, [0, 0, 0], 0, 32), (1, False))
            self.assertEqual(admitted(select, lanes, [0, 0, 0], 1, 65), (1, False))
            self.assertEqual(admitted(select, lanes, [1, 0, 0], 32, 32), (2, False))

    def test_seeded_differential(self):
        rng = random.Random(2305)
        for _ in range(4096):
            clocks = [rng.randrange(5) for _ in range(3)]
            lanes = [Lane(i, rng.randrange(3), rng.randrange(8),
                          rng.choice([None, 0, 1, 2, 3, i + 4]), rng.randrange(65))
                     for i in range(rng.randrange(65))]
            rng.shuffle(lanes)
            staged, limit = rng.randrange(65), rng.randrange(65)
            self.assertEqual(one_pass(lanes, clocks), two_pass(lanes, clocks))
            self.assertEqual(admitted(one_pass, lanes, clocks, staged, limit),
                             admitted(two_pass, lanes, clocks, staged, limit))
            self.assertEqual(one_pass(list(reversed(lanes)), clocks), one_pass(lanes, clocks))

    def test_scan_visits_not_timing(self):
        class Counted(list):
            visits = 0

            def __iter__(self):
                for lane in super().__iter__():
                    self.visits += 1
                    yield lane

        lanes = Counted(Lane(i, i % 3, i, i) for i in range(64))
        self.assertEqual(two_pass(lanes, [0, 0, 0]), 0)
        self.assertEqual(lanes.visits, 128)
        lanes.visits = 0
        self.assertEqual(one_pass(lanes, [0, 0, 0]), 0)
        self.assertEqual(lanes.visits, 64)


if __name__ == "__main__":
    unittest.main()
