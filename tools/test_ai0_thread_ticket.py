"""Title-free arithmetic review of the external EXT-05 thread-ticket algorithm.

This is a model, not shader execution or a proposed emitter patch. The
fragmented partition is a conditional counterexample, not an observed GPU.
"""
import itertools
import unittest
from collections import Counter


def legacy(waves, width):
    return [flat[0] // width * width + lane
            for flat in waves for lane in range(len(flat))]


def external_ticket(counts, width):
    """Model the two 16-bit accumulators in the external packed counter."""
    group = sum(counts)
    counter = 0
    out = []
    for count in counts:
        if not 0 < count <= width:
            raise ValueError("invalid active count")
        found = counter
        if count == width:
            counter += width
            base = found & 0xffff
        else:
            counter += count << 16
            base = group // width * width + (found >> 16)
        out.extend(range(base, base + count))
    return out


def exact_once(ids, group):
    """Count visits, including duplicates and out-of-range indices."""
    return Counter(ids) == Counter(range(group))


class ThreadTicketReview(unittest.TestCase):
    def test_tiled_32_by_2_reproduces_legacy_collision(self):
        waves = [list(range(16)) + list(range(32, 48)),
                 list(range(16, 32)) + list(range(48, 64))]
        before = legacy(waves, 32)
        self.assertEqual(len(set(before)), 32)
        self.assertFalse(exact_once(before, 64))
        self.assertTrue(exact_once(external_ticket([32, 32], 32), 64))

    def test_full_waves_and_single_tail_in_any_order(self):
        for width in (32, 64):
            for group in range(1, 1025):
                full, tail = divmod(group, width)
                counts = [width] * full
                if tail:
                    for pos in range(full + 1):
                        order = counts[:pos] + [tail] + counts[pos:]
                        self.assertTrue(exact_once(external_ticket(order, width), group),
                                        (width, group, pos))
                else:
                    self.assertTrue(exact_once(external_ticket(counts, width), group))

    def test_fragmented_waves_require_a_separate_contract(self):
        # Conditional: not a claim that a hardware implementation does this.
        for order in set(itertools.permutations([16, 16, 32])):
            got = external_ticket(order, 32)
            self.assertFalse(exact_once(got, 64))
            self.assertTrue(any(x >= 64 for x in got))

    def test_paired_stride_must_remain_64(self):
        for count in (1, 2, 4, 8, 16):
            paired = [wave * 64 + half * 32 + lane
                      for wave in range(count) for half in range(2)
                      for lane in range(32)]
            self.assertTrue(exact_once(paired, count * 64))
            if count > 1:
                wrong = [wave * 32 + half * 32 + lane
                         for wave in range(count) for half in range(2)
                         for lane in range(32)]
                self.assertFalse(exact_once(wrong, count * 64))

    def test_constant_store_does_not_detect_duplicate_visits(self):
        visits = list(range(64)) + [17]
        memory = [0] * 64
        for i in visits:
            memory[i] = 1
        self.assertEqual(memory, [1] * 64)
        self.assertFalse(exact_once(visits, 64))


if __name__ == "__main__":
    unittest.main()
