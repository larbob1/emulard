"""Review-only destination dispatch admission model. No GPU or source layout proof."""
from dataclasses import dataclass
import unittest
from itertools import product

MAX32 = (1 << 32) - 1
MAX_GROUP = 65535


@dataclass(frozen=True)
class Job:
    offset: int
    width: int
    height: int
    depth: int
    element: int
    pitch: int
    rows: int
    footprint_depth: int


def admit(jobs, expected, capacity):
    """Conservative destination-only gate, not a D3D footprint validator."""
    if expected <= 0 or len(jobs) != expected or not 0 < capacity <= MAX32:
        return None
    spans = []
    groups = []
    for j in jobs:
        if (j.element not in (1, 2, 4, 8, 16)
                or min(j.width, j.height, j.depth, j.pitch, j.rows, j.footprint_depth) <= 0
                or j.offset < 0 or j.offset % 512 or j.pitch % 256
                or j.height != j.rows or j.depth != j.footprint_depth):
            return None
        payload = j.width * j.element
        words = (payload + 3) // 4
        rounded = words * 4
        depth_pitch = j.pitch * j.rows
        end = j.offset + (j.depth - 1) * depth_pitch + (j.height - 1) * j.pitch + rounded
        dispatch = ((words + 63) // 64, j.height, j.depth)
        if (rounded > j.pitch or depth_pitch > MAX32 or end > capacity
                or any(g > MAX_GROUP for g in dispatch)):
            return None
        spans.append((j.offset, end))
        groups.append(dispatch)
    ordered = sorted(spans)
    if any(b > c for (_, b), (c, _) in zip(ordered, ordered[1:])):
        return None
    return groups


class DetilePlan(unittest.TestCase):
    def test_rounded_final_word_requires_real_capacity(self):
        job = Job(0, 5, 1, 1, 1, 256, 1, 1)
        self.assertIsNone(admit([job], 1, 5))
        self.assertEqual(admit([job], 1, 8), [(1, 1, 1)])

    def test_missing_or_overlapping_subresources_refused(self):
        a = Job(0, 8, 3, 1, 4, 256, 3, 1)
        b = Job(512, 8, 1, 1, 4, 256, 1, 1)
        c = Job(1024, 8, 1, 1, 4, 256, 1, 1)
        self.assertIsNone(admit([a], 2, 4096))
        self.assertIsNone(admit([a, b], 2, 4096))
        self.assertEqual(admit([a, c], 2, 4096), [(1, 3, 1), (1, 1, 1)])

    def test_dispatch_limit_and_dimensions(self):
        width = MAX_GROUP * 64
        pitch = width * 4
        self.assertEqual(admit([Job(0, width, 1, 1, 4, pitch, 1, 1)], 1, pitch),
                         [(MAX_GROUP, 1, 1)])
        self.assertIsNone(admit([Job(0, width + 1, 1, 1, 4, pitch + 256, 1, 1)],
                                1, pitch + 256))
        self.assertIsNone(admit([Job(0, 4, 1, 1, 1, 256, 2, 1)], 1, 512))

    def test_invalid_values(self):
        for job in (Job(1, 1, 1, 1, 1, 256, 1, 1),
                    Job(0, 1, 1, 1, 3, 256, 1, 1),
                    Job(0, 0, 1, 1, 1, 256, 1, 1),
                    Job(0, 1, 1, 1, 1, 255, 1, 1),
                    Job(0, 1, 1, 1, 1, 256, 1, 2)):
            self.assertIsNone(admit([job], 1, 1024))
        self.assertIsNone(admit([], 0, 1024))

    def test_small_dispatch_byte_oracle(self):
        for width, height, depth, elem, offset in product(
                (1, 2, 3, 5, 63, 64, 65), (1, 2, 3), (1, 2),
                (1, 2, 4, 8, 16), (0, 512)):
            pitch = ((width * elem + 255) // 256) * 256
            j = Job(offset, width, height, depth, elem, pitch, height, depth)
            writes = [offset + z * pitch * height + y * pitch + x * 4 + byte
                      for z in range(depth) for y in range(height)
                      for x in range((width * elem + 3) // 4) for byte in range(4)]
            self.assertEqual(len(writes), len(set(writes)))
            end = max(writes) + 1
            self.assertIsNotNone(admit([j], 1, end))
            self.assertIsNone(admit([j], 1, end - 1))


if __name__ == "__main__":
    unittest.main()
