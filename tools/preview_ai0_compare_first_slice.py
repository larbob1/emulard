#!/usr/bin/env python3
"""Review-only exact pinned compare boundary correction; no runtime registration.

Pass the exact raw shadow.rs and a NEW scratch output. This preview does not
modify the input or run the native regression. Reconcile prepared source
before integration.
"""
import argparse
import hashlib
from pathlib import Path

PIN = "4fa43df7932bb6692d164384cd28b1f08f3001ee"
OLD = "            (at - (start + at) % PIECE).max(from)"
NEW = "            at.saturating_sub((start + at) % PIECE).max(from)"
ANCHOR = "mod card_merge_tests {\n    use super::{Card, Shadow};"
MARKER = "fn ai0_parallel_compare_exact_changed_piece_ranges("
FIXTURE = Path(__file__).resolve().parent.parent / "probes/compare_first_slice_review.rs"

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
                        usedforsecurity=False).hexdigest()

def preview(data, fixture):
    if git_blob(data) != PIN:
        raise ValueError("unexpected raw source blob")
    text = data.decode("utf-8")
    if text.count(OLD) != 1 or text.count(ANCHOR) != 1:
        raise ValueError("unexpected source anchors")
    if MARKER in text or fixture.count(MARKER) != 1:
        raise ValueError("unexpected fixture marker")
    text = text.replace(OLD, NEW, 1).replace(ANCHOR, ANCHOR + "\n" + fixture, 1)
    return text.encode("utf-8")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    try:
        data = preview(args.source.read_bytes(), FIXTURE.read_text(encoding="utf-8"))
        with args.output.open("xb") as f:
            f.write(data)
    except (OSError, ValueError) as exc:
        ap.exit(1, f"preview refused: {type(exc).__name__}\n")
    print("Compare first-slice review postimage created; native test not run")

if __name__ == "__main__":
    main()
