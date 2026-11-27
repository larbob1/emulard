# SPDX-License-Identifier: GPL-3.0-or-later
"""Append-only rectangle slot scan preview; no production registration."""
import argparse
import hashlib
from pathlib import Path

PIN = "41380c23a61b93000c4886265c3063676ddc4864"
START = "    fn rectangles(&self, list: &HostList, count: u32, first: u32) -> bool {"
END = "\n    }\n\n    pub(crate) fn draw_indexed("
OLD = "        for slot in 0..32 {\n            let elements: Vec<(u32, u32)> = p\n                .inputs\n                .iter()\n                .filter(|e| e.slot == slot && !e.per_instance)\n                .map(|e| (e.offset, e.format))\n                .collect();\n            if elements.is_empty() {\n                continue;\n            }\n"
NEW = "        let mut active = 0u32;\n        for e in &p.inputs {\n            if e.slot < 32 && !e.per_instance {\n                active |= 1u32 << e.slot;\n            }\n        }\n        while active != 0 {\n            let slot = active.trailing_zeros();\n            active &= active - 1;\n            let elements: Vec<(u32, u32)> = p\n                .inputs\n                .iter()\n                .filter(|e| e.slot == slot && !e.per_instance)\n                .map(|e| (e.offset, e.format))\n                .collect();\n            if elements.is_empty() {\n                continue;\n            }\n"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def clone(source):
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("rectangle method boundaries mismatch")
    a = source.index(START)
    b = source.index(END, a) + len("\n    }")
    method = source[a:b]
    if method.count(OLD) != 1 or "rectangles_active_slots" in source:
        raise ValueError("slot enumeration anchor or prior candidate mismatch")
    return method.replace(START, START.replace("rectangles(", "rectangles_active_slots("), 1).replace(OLD, NEW, 1)


def preview(source, expected=PIN):
    if blob(source) != expected:
        raise ValueError("draw source blob mismatch")
    candidate = clone(source.decode("utf-8"))
    return source + b"\n#[cfg(test)]\nimpl State {\n" + candidate.encode() + b"\n}\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    data = preview(a.source.read_bytes())
    with a.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
