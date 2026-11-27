# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only texture offset table experiment; no builder registration."""
import argparse
import hashlib
from pathlib import Path

PIN = "fa719c93953d9e6589c4d2cd27a13d773863c316"
OLD = "fn spread(bits: &[u32]) -> Vec<u32> {\n    (0..1u32 << bits.len())\n        .map(|c| {\n            bits.iter()\n                .enumerate()\n                .map(|(i, &to)| ((c >> i) & 1) << to)\n                .sum()\n        })\n        .collect()\n}"
NEW = "fn spread_incremental(bits: &[u32]) -> Vec<u32> {\n    // The caller supplies distinct address-bit positions within a block.\n    // Extend the previous prefix in increasing coordinate order.\n    let count = 1u32 << bits.len();\n    let mut offsets = Vec::with_capacity(count as usize);\n    offsets.push(0u32);\n    for &to in bits {\n        let increment = 1u32 << to;\n        let half = offsets.len();\n        for i in 0..half {\n            let next = offsets[i] + increment;\n            offsets.push(next);\n        }\n    }\n    offsets\n}"
FIXTURE = Path(__file__).resolve().parent.parent / "probes/texture_spread_review.rs"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def preview(source, fixture, expected=PIN):
    if blob(source) != expected:
        raise ValueError("texture source blob mismatch")
    text = source.decode("utf-8")
    if text.count(OLD) != 1 or "spread_incremental" in text:
        raise ValueError("spread anchor or prior candidate mismatch")
    if not fixture.startswith(b"#[cfg(test)]\nmod ai0_texture_spread_review"):
        raise ValueError("fixture marker mismatch")
    return source + b"\n#[cfg(test)]\n" + NEW.encode() + b"\n" + fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = preview(args.source.read_bytes(), FIXTURE.read_bytes())
    # This is an append-only preview of a disposable source copy.
    with args.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
