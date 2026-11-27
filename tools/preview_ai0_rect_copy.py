# SPDX-License-Identifier: GPL-3.0-or-later
"""Append-only CPU rectangle copy experiment for disposable source copies."""
import argparse
import hashlib
from pathlib import Path

PIN = "3f73ee71ec98b59472be17fbf48f9198424fcb74"
START = "pub(crate) fn expand_rects("
END = "\n}\n\n#[derive(Clone, Copy)]"
OLD = "        for (slot, i) in [0, 1, 2, 0, 2].into_iter().enumerate() {\n            out[slot * stride..(slot + 1) * stride].copy_from_slice(v(i));\n        }\n"
NEW = "        out[..3 * stride].copy_from_slice(rect);\n        out[3 * stride..4 * stride].copy_from_slice(v(0));\n        out[4 * stride..5 * stride].copy_from_slice(v(2));\n"
FIXTURE = Path(__file__).resolve().parent.parent / "probes/rect_copy_review.rs"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def clone(source):
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("rectangle function boundaries mismatch")
    a = source.index(START)
    b = source.index(END, a) + len("\n}")
    original = source[a:b]
    if original.count(OLD) != 1 or "expand_rects_coalesced" in source:
        raise ValueError("rectangle copy anchor or prior candidate mismatch")
    return original.replace(START, "fn expand_rects_coalesced(", 1).replace(OLD, NEW, 1)


def preview(source, fixture, expected=PIN):
    if blob(source) != expected:
        raise ValueError("primitive source blob mismatch")
    if not fixture.startswith(b"#[cfg(test)]\nmod ai0_rect_copy_review"):
        raise ValueError("fixture marker mismatch")
    return source + b"\n#[cfg(test)]\n" + clone(source.decode("utf-8")).encode() + b"\n" + fixture


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    data = preview(a.source.read_bytes(), FIXTURE.read_bytes())
    with a.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
