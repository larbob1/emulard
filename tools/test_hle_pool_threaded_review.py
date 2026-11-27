"""Title-free threaded model for xasync Pool admission; not Rust/native evidence."""
from collections import deque
import threading
import unittest

LIMIT = 3


class Pool:
    def __init__(self, reserve):
        self.reserve = reserve
        lock = threading.RLock()
        self.cv = threading.Condition(lock)
        self.changed = threading.Condition(lock)
        self.queue = deque()
        self.idle = self.starting = self.requested = self.failed = 0
        self.empty_wakes = 0
        self.claimed = []
        self.completed = []
        self.errors = []
        self.workers = []
        self.gates = []
        self.closed = False

    def submit(self, number, callback=lambda: None, fail=False):
        with self.cv:
            assert not self.closed
            self.queue.append((number, callback))
            capacity = self.idle + (self.starting if self.reserve else 0)
            if len(self.queue) > capacity:
                self.requested += 1
                self.starting += 1
                gate = threading.Event()
                worker = threading.Thread(target=self.work, args=(gate,), daemon=True)
                try:
                    if fail:
                        raise RuntimeError('injected start failure')
                    worker.start()
                except RuntimeError:
                    self.starting -= 1
                    self.failed += 1
                    self.cv.notify()
                    self.changed.notify_all()
                    raise
                self.gates.append(gate)
                self.workers.append(worker)
            else:
                self.cv.notify()
            self.changed.notify_all()

    def work(self, gate):
        gate.wait()
        first = True
        while True:
            with self.cv:
                if first:
                    self.starting -= 1
                    first = False
                    self.changed.notify_all()
                while not self.queue and not self.closed:
                    self.idle += 1
                    self.changed.notify_all()
                    self.cv.wait()
                    self.idle -= 1
                    if not self.queue and not self.closed:
                        self.empty_wakes += 1
                if self.closed:
                    return
                number, callback = self.queue.popleft()
                self.claimed.append(number)
                self.changed.notify_all()
            try:
                callback()
            except Exception as exc:
                with self.cv:
                    self.errors.append(exc)
            finally:
                with self.cv:
                    self.completed.append(number)
                    self.changed.notify_all()

    def until(self, predicate):
        with self.cv:
            if not self.changed.wait_for(predicate, timeout=LIMIT):
                raise AssertionError('fixture deadline expired')

    def close(self):
        with self.cv:
            self.closed = True
            self.cv.notify_all()
            for gate in self.gates:
                gate.set()
        for worker in self.workers:
            worker.join(LIMIT)
            if worker.is_alive():
                raise AssertionError('fixture worker did not stop')
        if self.errors:
            raise AssertionError(self.errors)


class ThreadedReview(unittest.TestCase):
    def pool(self, reserve):
        pool = Pool(reserve)
        self.addCleanup(pool.close)
        return pool

    def test_controlled_drain_before_pending_start(self):
        for reserve, expected in [(False, 3), (True, 2)]:
            with self.subTest(reserve=reserve):
                p = self.pool(reserve)
                p.submit(1)
                p.submit(2)
                p.gates[0].set()
                p.until(lambda: p.idle == 1 and len(p.completed) == 2)
                self.assertEqual(p.starting, 1)
                # Fixture lock holds both submits in one forced interleaving.
                with p.cv:
                    p.submit(3)
                    p.submit(4)
                    self.assertEqual(p.requested, expected)
                for gate in p.gates:
                    gate.set()
                p.until(lambda: len(p.completed) == 4)
                self.assertEqual(p.claimed, [1, 2, 3, 4])
                self.assertCountEqual(p.completed, [1, 2, 3, 4])

    def test_reentrant_blocked_callback_can_get_another_worker(self):
        for reserve in (False, True):
            p = self.pool(reserve)
            released = threading.Event()
            entered = threading.Event()

            def first():
                p.submit(2, released.set)
                entered.set()
                if not released.wait(LIMIT):
                    raise AssertionError('blocked callback starved')

            p.submit(1, first)
            p.gates[0].set()
            self.assertTrue(entered.wait(LIMIT))
            self.assertEqual(p.requested, 2)
            p.gates[1].set()
            p.until(lambda: len(p.completed) == 2)
            self.assertEqual(p.claimed, [1, 2])
            self.assertCountEqual(p.completed, [1, 2])

    def test_empty_notification_rechecks_predicate(self):
        for reserve in (False, True):
            p = self.pool(reserve)
            p.submit(1)
            p.gates[0].set()
            p.until(lambda: p.idle == 1)
            with p.cv:
                p.cv.notify_all()
            p.until(lambda: p.empty_wakes == 1 and p.idle == 1)
            self.assertEqual(p.claimed, [1])
            p.submit(2)
            p.until(lambda: len(p.completed) == 2)
            self.assertEqual(p.requested, 1)
            self.assertEqual(p.claimed, [1, 2])

    def test_failed_start_rolls_back_reservation(self):
        for reserve in (False, True):
            p = self.pool(reserve)
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                p.submit(1, fail=True)
            self.assertEqual((p.starting, p.failed), (0, 1))
            # Recovery is fixture-only: a later submit provides capacity.
            p.submit(2)
            p.gates[0].set()
            p.until(lambda: len(p.completed) == 2)
            self.assertEqual(p.claimed, [1, 2])
            self.assertEqual(p.requested, 2)


if __name__ == '__main__':
    unittest.main()
