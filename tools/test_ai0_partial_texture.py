"""Review-only partial texture capture/publication model, not runtime code."""
from dataclasses import dataclass
from enum import Enum, auto
from itertools import product
import unittest


class Kind(Enum):
    READ = auto()
    HOLE = auto()
    ERROR = auto()


@dataclass(frozen=True)
class Piece:
    kind: Kind
    size: int
    data: bytes = b""


def capture(pieces, size):
    """Return complete private bytes and explicit coverage, or refuse.

    HOLE means independently established unmapped memory, not a failed read.
    This model assumes the caller has a coherent mapping snapshot.
    """
    out = bytearray()
    readable = 0
    for p in pieces:
        if p.size <= 0 or len(out) + p.size > size:
            return None
        if p.kind is Kind.READ and len(p.data) == p.size:
            out.extend(p.data)
            readable += p.size
        elif p.kind is Kind.HOLE and not p.data:
            out.extend(bytes(p.size))
        else:
            return None
    if len(out) != size or readable == 0:
        return None
    return bytes(out), readable


@dataclass
class Staging:
    valid: bool = False
    data: bytes = b""
    fingerprint: bytes | None = None
    dirty: bool = False
    asked: int = 7


def first_fill(staging, pieces, size, captured_epoch, live_epoch,
               guard, detile_ok):
    """Model conservative eligibility, not actual mapping or detiling.

    The private detile result is assumed to be identity for this byte oracle.
    No existing valid staging is replaced by this first-fill-only fallback.
    """
    result = capture(pieces, size)
    if (staging.valid or result is None or not guard
            or captured_epoch != live_epoch or captured_epoch % 2
            or not detile_ok):
        staging.asked = 0
        return False
    data, _ = result
    staging.data = data
    staging.fingerprint = data  # exact bytes in this model, not a real hash
    staging.valid = True
    staging.dirty = True
    staging.asked = 0  # do not suppress the next mapping/coverage check
    return True


class PartialTexture(unittest.TestCase):
    def test_mapped_zero_is_not_a_hole(self):
        self.assertEqual(capture([Piece(Kind.READ, 2, b"\0\0"),
                                  Piece(Kind.HOLE, 2)], 4), (b"\0"*4, 2))
        self.assertIsNone(capture([Piece(Kind.HOLE, 4)], 4))

    def test_fresh_bytes_and_zero_holes(self):
        self.assertEqual(capture([Piece(Kind.HOLE, 1),
                                  Piece(Kind.READ, 2, b"ab"),
                                  Piece(Kind.HOLE, 1)], 4), (b"\0ab\0", 2))
        self.assertIsNone(capture([Piece(Kind.READ, 3, b"ab"),
                                   Piece(Kind.HOLE, 1)], 4))
        self.assertIsNone(capture([Piece(Kind.ERROR, 4)], 4))
        self.assertIsNone(capture([Piece(Kind.HOLE, 2)], 4))

    def test_hash_absence_does_not_mean_first_fill(self):
        # Existing watch path can detile successfully without assigning hash.
        s = Staging(valid=True, data=b"old!", fingerprint=None, dirty=True)
        self.assertFalse(first_fill(s, [Piece(Kind.READ, 4, b"new!")],
                                    4, 2, 2, True, True))
        self.assertEqual((s.data, s.fingerprint, s.dirty, s.asked),
                         (b"old!", None, True, 0))

    def test_reject_preserves_publication_state(self):
        for guard, same_epoch, stable, detile_ok in product((False, True), repeat=4):
            s = Staging()
            epoch = 2 if stable else 3
            accepted = first_fill(s, [Piece(Kind.READ, 2, b"ab"),
                                      Piece(Kind.HOLE, 2)], 4,
                                  epoch, epoch if same_epoch else epoch+2,
                                  guard, detile_ok)
            expected = guard and same_epoch and stable and detile_ok
            self.assertEqual(accepted, expected)
            self.assertEqual(s.asked, 0)
            self.assertEqual((s.valid, s.dirty), (expected, expected))
            self.assertEqual(s.data, b"ab\0\0" if expected else b"")
            self.assertEqual(s.fingerprint, b"ab\0\0" if expected else None)

    def test_coverage_matrix(self):
        variants = [Piece(Kind.READ, 1, b"\0"), Piece(Kind.READ, 1, b"x"),
                    Piece(Kind.HOLE, 1), Piece(Kind.ERROR, 1)]
        for pieces in product(variants, repeat=4):
            result = capture(pieces, 4)
            if any(p.kind is Kind.ERROR for p in pieces):
                self.assertIsNone(result)
            else:
                n = sum(p.kind is Kind.READ for p in pieces)
                expected = bytes(p.data[0] if p.kind is Kind.READ else 0
                                 for p in pieces)
                self.assertEqual(result, (expected, n) if n else None)


if __name__ == "__main__":
    unittest.main()
