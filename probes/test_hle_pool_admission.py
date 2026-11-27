"""P18/P24 deterministic admission model; not runtime or timing evidence."""
from collections import deque
import unittest


class Pool:
    def __init__(self, reserve):
        self.reserve = reserve
        self.queue = deque()
        self.idle = 0
        self.starting = 0
        self.active = set()
        self.spawns = 0
        self.claimed = []

    def submit(self, task):
        self.queue.append(task)
        capacity = self.idle + (self.starting if self.reserve else 0)
        if len(self.queue) > capacity:
            self.starting += 1
            self.spawns += 1

    def claim(self):
        if not self.queue:
            self.idle += 1
            return None
        task = self.queue.popleft()
        assert task not in self.active
        self.active.add(task)
        self.claimed.append(task)
        return task

    def start(self):
        assert self.starting > 0
        self.starting -= 1
        return self.claim()

    def wake(self):
        assert self.idle > 0
        self.idle -= 1
        return self.claim()

    def finish(self, task):
        self.active.remove(task)
        return self.claim()


class AdmissionTests(unittest.TestCase):
    def test_pending_worker_reused_after_active_worker_drains_queue(self):
        for reserve, expected in [(False, 3), (True, 2)]:
            p = Pool(reserve)
            p.submit(1)
            p.submit(2)
            self.assertEqual(p.start(), 1)
            self.assertEqual(p.finish(1), 2)
            self.assertIsNone(p.finish(2))
            self.assertEqual((p.idle, p.starting), (1, 1))
            p.submit(3)
            p.submit(4)
            self.assertEqual(p.spawns, expected)
            self.assertEqual(p.wake(), 3)
            self.assertEqual(p.start(), 4)
            self.assertEqual(p.claimed, [1, 2, 3, 4])

    def test_fresh_burst_does_not_reduce_spawn_count(self):
        for reserve in (False, True):
            p = Pool(reserve)
            for n in range(8):
                p.submit(n)
            self.assertEqual(p.spawns, 8)

    def test_pending_start_is_not_active_callback_capacity(self):
        p = Pool(True)
        p.submit(1)
        self.assertEqual(p.start(), 1)
        p.submit(2)
        self.assertEqual(p.spawns, 2)
        self.assertEqual(p.start(), 2)
        self.assertEqual(p.active, {1, 2})

    def test_idle_worker_can_steal_work_before_new_worker_starts(self):
        p = Pool(True)
        p.submit(1)
        p.submit(2)
        self.assertEqual(p.start(), 1)
        self.assertEqual(p.finish(1), 2)
        self.assertIsNone(p.start())
        self.assertIsNone(p.finish(2))
        self.assertEqual((p.idle, p.starting, len(p.active)), (2, 0, 0))
        self.assertEqual(p.claimed, [1, 2])

    def test_fifo_claims_with_interleaved_submit_and_completion(self):
        p = Pool(True)
        p.submit(1)
        p.submit(2)
        self.assertEqual(p.start(), 1)
        p.submit(3)
        self.assertEqual(p.finish(1), 2)
        self.assertEqual(p.start(), 3)
        self.assertIsNone(p.finish(2))
        self.assertIsNone(p.start())
        self.assertIsNone(p.finish(3))
        p.submit(4)
        self.assertEqual(p.wake(), 4)
        self.assertEqual(p.claimed, [1, 2, 3, 4])
        self.assertEqual(p.spawns, 3)


if __name__ == '__main__':
    unittest.main()
