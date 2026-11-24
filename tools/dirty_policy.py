#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reference policy for completion-scoped dirty pages; not a runtime hook."""
from dataclasses import dataclass, field

PAGE = 65536

@dataclass
class Submission:
    serial: int
    dirty: set[int] = field(default_factory=set)
    missed: set[int] = field(default_factory=set)
    complete: bool = False

    def mark(self, address, size, mapped=True):
        if self.complete:
            raise ValueError("completed submission")
        if address < 0 or size < 0 or address + size > (1 << 40):
            raise ValueError("invalid address range")
        if not size:
            return
        pages = range(address // PAGE, (address + size - 1) // PAGE + 1)
        (self.dirty if mapped else self.missed).update(pages)

    def finish(self, serial):
        if serial != self.serial or self.complete:
            raise ValueError("wrong or reused completion")
        self.complete = True

    def ranges(self, declarations):
        """(start,end,fully instrumented,dependency known) half-open ranges.

        If any missing page was encountered, dependent instrumented writes
        are withheld, not committed. Independent or untracked writes are
        always compared conservatively. This model assumes the caller can
        actually prove independence; unknown dependency is dependent.
        """
        if not self.complete:
            raise ValueError("GPU has not completed")
        compare, withheld = [], []
        for start, end, tracked, independent in declarations:
            if not 0 <= start <= end <= (1 << 40):
                raise ValueError("invalid declaration")
            if start == end:
                continue
            if not tracked:
                compare.append((start, end))
                continue
            if self.missed and not independent:
                withheld.append((start, end))
                continue
            for page in sorted(self.dirty):
                lo, hi = max(start, page * PAGE), min(end, (page + 1) * PAGE)
                if lo < hi:
                    compare.append((lo, hi))
        return compare, withheld

def merge_bytes(before, gpu, cpu):
    """Preserve CPU changes outside the actual GPU byte differences."""
    if len(before) != len(gpu) or len(gpu) != len(cpu):
        raise ValueError("length mismatch")
    return bytes(g if g != b else c for b, g, c in zip(before, gpu, cpu))
