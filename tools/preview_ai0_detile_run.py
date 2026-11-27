# SPDX-License-Identifier: GPL-3.0-or-later
"""Append a test-only detile walker to an exact pinned texture source.

Not registered by the runtime builder; writes only an explicitly named output.
Never apply to production or a live checkout. Use a disposable checkout.
"""
import argparse
import hashlib
from pathlib import Path

PIN = "fa719c93953d9e6589c4d2cd27a13d773863c316"
START = "    fn walk<const DETILE: bool>("
END = "\n    }\n}\n\nfn copy_run"
OLD = "        let mut runs = Vec::new();\n        if !linear {\n            let mut first_linear = 0;\n            let mut first_tiled = self.column(m, 0) as usize;\n            for x in 1..m.width {\n                let offset = self.column(m, x) as usize;\n                let at = x as usize * n;\n                if offset != first_tiled + (at - first_linear) {\n                    runs.push((first_tiled, first_linear, at - first_linear));\n                    first_tiled = offset;\n                    first_linear = at;\n                }\n            }\n            runs.push((first_tiled, first_linear, bytes - first_linear));\n        }\n        // A mip can end partway through the last run. Check the other runs\n        // once so each row can copy them as fixed-size chunks.\n        let (body, last) = runs.split_at(runs.len().saturating_sub(1));\n        let chunk_size = body.first().map(|run| run.2).filter(|&size| {\n            body.iter()\n                .all(|&(offset, _, len)| len == size && offset.is_multiple_of(size))\n        });\n"
NEW = "        let mut runs = Vec::new();\n        let mut last = None;\n        if !linear {\n            let mut first_linear = 0;\n            let mut first_tiled = self.column(m, 0) as usize;\n            for x in 1..m.width {\n                let offset = self.column(m, x) as usize;\n                let at = x as usize * n;\n                if offset != first_tiled + (at - first_linear) {\n                    runs.push((first_tiled, first_linear, at - first_linear));\n                    first_tiled = offset;\n                    first_linear = at;\n                }\n            }\n            last = Some((first_tiled, first_linear, bytes - first_linear));\n        }\n        // A mip can end partway through the last run. Check the other runs\n        // once so each row can copy them as fixed-size chunks.\n        let body = runs.as_slice();\n        let last = last.as_slice();\n        let chunk_size = body.first().map(|run| run.2).filter(|&size| {\n            body.iter()\n                .all(|&(offset, _, len)| len == size && offset.is_multiple_of(size))\n        });\n"
FIXTURE = Path(__file__).resolve().parent.parent / "probes/detile_last_run_review.rs"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def clone_method(source):
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("walk boundaries mismatch")
    start = source.index(START)
    end = source.index(END, start) + len("\n    }")
    method = source[start:end]
    if method.count(OLD) != 1 or "walk_last_inline" in source:
        raise ValueError("walk planning block mismatch")
    return method.replace(START, START.replace("walk<", "walk_last_inline<"), 1).replace(OLD, NEW, 1)


def preview(data, fixture, expected=PIN):
    if blob(data) != expected:
        raise ValueError("texture source blob mismatch")
    clone = clone_method(data.decode("utf-8"))
    if not fixture.startswith(b"#[cfg(test)]\nmod ai0_detile_last_run_review"):
        raise ValueError("fixture marker mismatch")
    return data + b"\n#[cfg(test)]\nimpl Layout {\n" + clone.encode() + b"\n}\n" + fixture


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = preview(a.source.read_bytes(), FIXTURE.read_bytes())
    # Exclusive creation prevents accidentally overwriting the original.
    with a.output.open("xb") as f:
        f.write(result)


if __name__ == "__main__":
    main()
