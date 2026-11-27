"""Read-only overlap triage for three explicitly supplied, title-free source files.

Example (in an isolated prepared checkout):
  python tools/ai0_source_overlap.py BASE LEFT RIGHT --base-sha256 HASH

HASH is the independently recorded SHA-256 of the common prepared base file.
Compare only the same relative source file from independently prepared snapshots.
Output uses zero-based, half-open base line ranges; [n,n) is an insertion
before line n (or EOF). Insertion at either endpoint is flagged conservatively.
No source lines or input paths are printed. Inputs must be stable, trusted UTF-8
text, at most 256 KiB / 4000 lines each. Exact bytes, including line endings, matter.

Exit 0: at most one side changed; 1: both changed (review); 2: invalid input.
A disjoint result is NOT a merge approval: alignment is heuristic, repeated
lines may shift matches, omitted files and semantic dependencies are invisible.
Hashes identify supplied bytes, not provenance. Never use title data.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
import re

MAX_BYTES = 256 * 1024
MAX_LINES = 4000


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    replacement: tuple[bytes, ...]


def checked_lines(data: bytes) -> list[bytes]:
    if len(data) > MAX_BYTES or b"\x00" in data:
        raise ValueError("size limit or non-text input")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeError:
        raise ValueError("invalid UTF-8") from None
    lines = data.splitlines(keepends=True)
    if len(lines) > MAX_LINES:
        raise ValueError("line limit")
    return lines


def edits(base: list[bytes], changed: list[bytes]) -> list[Edit]:
    if base == changed:
        return []
    return [
        Edit(i, j, tuple(changed[k:l]))
        for tag, i, j, k, l in SequenceMatcher(
            None, base, changed, autojunk=False
        ).get_opcodes()
        if tag != "equal"
    ]


def touches(a: Edit, b: Edit) -> bool:
    if a.start == a.end:
        return b.start <= a.start <= b.end
    if b.start == b.end:
        return a.start <= b.start <= a.end
    return max(a.start, b.start) < min(a.end, b.end)


def analyze(base: bytes, left: bytes, right: bytes, expected_base: str):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_base):
        raise ValueError("expected base SHA-256 must be 64 hex digits")
    original, lhs, rhs = map(checked_lines, (base, left, right))
    digests = tuple(sha256(x).hexdigest() for x in (base, left, right))
    if digests[0] != expected_base.lower():
        raise ValueError("base SHA-256 mismatch")
    a, b = edits(original, lhs), edits(original, rhs)
    # Sweep sorted non-overlapping edits. Keep the inclusive boundary for
    # insertions; adjacent replacements are filtered by touches().
    overlaps = []
    cursor = 0
    for x in a:
        while cursor < len(b) and b[cursor].end < x.start:
            cursor += 1
        for y in b[cursor:]:
            if y.start > x.end:
                break
            if touches(x, y):
                overlaps.append((x, y, x == y))
    status = (
        "OVERLAP_REVIEW" if overlaps else
        "SAME_FILE_REVIEW" if a and b else
        "ONE_SIDE_ONLY" if a or b else "UNCHANGED"
    )
    return status, digests, a, b, overlaps


def read_bounded(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError("input is not a regular file")
    with path.open("rb") as f:
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("size limit")
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "left", "right"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--base-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        status, hashes, left, right, pairs = analyze(
            *(read_bounded(p) for p in (args.base, args.left, args.right)),
            args.base_sha256,
        )
    except OSError:
        print("INVALID_INPUT: cannot read input")
        return 2
    except ValueError as exc:
        print(f"INVALID_INPUT: {exc}")
        return 2
    print(f"status={status}")
    for label, digest in zip(("base", "left", "right"), hashes):
        print(f"{label}_sha256={digest}")
    for label, changes in (("left", left), ("right", right)):
        for e in changes:
            print(f"{label} [{e.start},{e.end}) new_lines={len(e.replacement)}")
    for a, b, identical in pairs:
        print(f"overlap left=[{a.start},{a.end}) right=[{b.start},{b.end}) "
              f"identical={int(identical)}")
    print(f"overlap_pairs={len(pairs)}; triage_only=1")
    return int(bool(left and right))


if __name__ == "__main__":
    raise SystemExit(main())
