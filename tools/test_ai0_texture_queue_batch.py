"""Review-only texture queue subset and interleaving counterexamples."""
from dataclasses import dataclass
from itertools import product
import unittest


@dataclass
class Entry:
    write: int
    due: int
    looks: int = 0
    mapped: int = 0
    checked: tuple | None = None


class Queue:
    def __init__(self):
        self.slots = {}
        self.held = {}
        self.writes = 0

    def write(self, slot, due):
        self.writes += 1
        self.slots[slot] = Entry(self.writes, due)
        return self.writes

    def tell(self, slot, write, kind, value):
        e = self.slots.get(slot)
        if e is None or e.write != write:
            return
        if kind == "done":
            del self.slots[slot]
        elif kind == "later":
            frame, most = value
            e.due = frame + min(1 << min(e.looks, 16), max(most, 1))
            e.looks = min(e.looks + 1, 255)
        elif kind == "hold":
            e.due = max(e.due, value)
            self.held[slot] = write
        elif kind == "partly":
            e.due, e.looks, e.mapped = value[0], 0, max(value[1], 1)
        elif kind == "recheck":
            e.due, e.looks, e.mapped, e.checked = value[0], 1, 0, value[1]
        else:
            raise ValueError(kind)

    def room(self, frame):
        held, self.held = self.held, {}
        for slot, write in held.items():
            e = self.slots.get(slot)
            if e is not None and e.write == write:
                e.due = min(e.due, frame)

    def flush(self, pending):
        for item in pending:
            self.tell(*item)
        pending.clear()


class TextureBatch(unittest.TestCase):
    def test_sequential_batch_preserves_state_without_interference(self):
        actions = [("done", None), ("later", (10, 16)), ("hold", 30),
                   ("partly", (12, 4096)), ("recheck", (14, (100, 64, 9)))]
        for first, second, third in product(actions, repeat=3):
            a, b = Queue(), Queue()
            for q in (a, b):
                q.write(0, 1)
                q.write(1, 2)
            items = [(0, 1, *first), (1, 2, *second), (0, 1, *third)]
            for item in items:
                a.tell(*item)
            b.flush(items)
            self.assertEqual((a.slots, a.held), (b.slots, b.held))
            self.assertEqual(items, [])

    def test_superseded_write_cannot_modify_new_entry(self):
        for kind, value in [("done", None), ("hold", 30), ("later", (10, 16)),
                            ("partly", (12, 4096)), ("recheck", (14, (100, 64, 9)))]:
            q = Queue()
            old = q.write(0, 1)
            new = q.write(0, 2)
            q.flush([(0, old, kind, value)])
            self.assertEqual(q.slots[0], Entry(new, 2))
            self.assertEqual(q.held, {})

    def test_room_between_compute_and_flush_changes_retry(self):
        immediate, delayed = Queue(), Queue()
        for q in (immediate, delayed):
            q.write(0, 1)
        item = (0, 1, "hold", 100)
        immediate.tell(*item)
        immediate.room(2)
        delayed.room(2)
        delayed.flush([item])
        self.assertEqual(immediate.slots[0].due, 2)
        self.assertEqual(delayed.slots[0].due, 100)
        self.assertEqual(delayed.held, {0: 1})

    def test_write_mark_does_not_validate_checked_metadata(self):
        q = Queue()
        write = q.write(0, 1)
        q.tell(0, write, "recheck", (2, (100, 64, 7)))
        cached = q.slots[0].checked
        q.tell(0, write, "recheck", (4, (100, 64, 9)))
        self.assertEqual(q.slots[0].write, write)
        self.assertNotEqual(q.slots[0].checked, cached)

    def test_partial_tail_flush_and_unprocessed_slots(self):
        for processed in range(33):
            q = Queue()
            for slot in range(33):
                q.write(slot, 1)
            pending = []
            for slot in range(processed):
                pending.append((slot, slot + 1, "done", None))
                if len(pending) == 16:
                    q.flush(pending)
            q.flush(pending)
            self.assertEqual(list(q.slots), list(range(processed, 33)))
            self.assertFalse(pending)


if __name__ == "__main__":
    unittest.main()
