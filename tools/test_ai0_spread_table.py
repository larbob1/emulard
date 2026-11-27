# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable parity of exact original/candidate functions, not full layout."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from preview_ai0_spread_table import OLD, NEW, FIXTURE, blob, preview

# Axis vectors derived from the pinned MICRO entries and pattern extension
# order. Actual-source native fixture independently invokes pattern itself.
AXES = """
const AXES: &[&[u32]] = &[
    &[0,1,2,3],
    &[4,5,6,7],
    &[],
    &[0,1,2,3,9,11],
    &[4,5,6,7,8,10],
    &[],
    &[0,1,2,3,9,11,13,15],
    &[4,5,6,7,8,10,12,14],
    &[],
    &[1,2,3,7],
    &[4,5,6],
    &[],
    &[1,2,3,7,9,11],
    &[4,5,6,8,10],
    &[],
    &[1,2,3,7,9,11,13,15],
    &[4,5,6,8,10,12,14],
    &[],
    &[2,3,7],
    &[4,5,6],
    &[],
    &[2,3,7,9,11],
    &[4,5,6,8,10],
    &[],
    &[2,3,7,9,11,13,15],
    &[4,5,6,8,10,12,14],
    &[],
    &[3,6,7],
    &[4,5],
    &[],
    &[3,6,7,9,11],
    &[4,5,8,10],
    &[],
    &[3,6,7,9,11,13,15],
    &[4,5,8,10,12,14],
    &[],
    &[6,7],
    &[4,5],
    &[],
    &[6,7,9,11],
    &[4,5,8,10],
    &[],
    &[6,7,9,11,13,15],
    &[4,5,8,10,12,14],
    &[],
    &[0,1,2,6],
    &[4,3,5,7],
    &[],
    &[0,1,2,6,9,11],
    &[4,3,5,7,8,10],
    &[],
    &[0,1,2,6,9,11,13,15],
    &[4,3,5,7,8,10,12,14],
    &[],
    &[1,2,3,7],
    &[4,5,6],
    &[],
    &[1,2,3,7,9,11],
    &[4,5,6,8,10],
    &[],
    &[1,2,3,7,9,11,13,15],
    &[4,5,6,8,10,12,14],
    &[],
    &[2,3,6],
    &[4,5,7],
    &[],
    &[2,3,6,9,11],
    &[4,5,7,8,10],
    &[],
    &[2,3,6,9,11,13,15],
    &[4,5,7,8,10,12,14],
    &[],
    &[3,5,6],
    &[4,7],
    &[],
    &[3,5,6,9,11],
    &[4,7,8,10],
    &[],
    &[3,5,6,9,11,13,15],
    &[4,7,8,10,12,14],
    &[],
    &[4,6],
    &[5,7],
    &[],
    &[4,6,9,11],
    &[5,7,8,10],
    &[],
    &[4,6,9,11,13,15],
    &[5,7,8,10,12,14],
    &[],
    &[0,1,6],
    &[3,5],
    &[2,4,7],
    &[0,1,6,9],
    &[3,5,8,11],
    &[2,4,7,10],
    &[0,1,6,9,12,15],
    &[3,5,8,11,14],
    &[2,4,7,10,13],
    &[1,6],
    &[3,5],
    &[2,4,7],
    &[1,6,9],
    &[3,5,8,11],
    &[2,4,7,10],
    &[1,6,9,12,15],
    &[3,5,8,11,14],
    &[2,4,7,10,13],
    &[2,6],
    &[3,5],
    &[4,7],
    &[2,6,9],
    &[3,5,8,11],
    &[4,7,10],
    &[2,6,9,12,15],
    &[3,5,8,11,14],
    &[4,7,10,13],
    &[3,6],
    &[5],
    &[4,7],
    &[3,6,9],
    &[5,8,11],
    &[4,7,10],
    &[3,6,9,12,15],
    &[5,8,11,14],
    &[4,7,10,13],
    &[6],
    &[5],
    &[4,7],
    &[6,9],
    &[5,8,11],
    &[4,7,10],
    &[6,9,12,15],
    &[5,8,11,14],
    &[4,7,10,13]
];
"""
RUST_TESTS = """
fn check(bits: &[u32]) {
    let before = spread(bits);
    let after = spread_incremental(bits);
    assert_eq!(before, after, "{bits:?}");
    assert_eq!(after.len(), 1usize << bits.len());
    // Independent per-coordinate oracle, using disjoint bit positions.
    for (i, &value) in after.iter().enumerate() {
        let mut expected = 0u32;
        for (coordinate_bit, &address_bit) in bits.iter().enumerate() {
            if i & (1 << coordinate_bit) != 0 {
                expected |= 1u32 << address_bit;
            }
        }
        assert_eq!(value, expected);
    }
}

#[test]
fn pinned_axis_snapshots() {
    assert_eq!(AXES.len(), 135);
    for bits in AXES {
        check(bits);
    }
}

#[test]
fn all_small_axis_subsets_in_multiple_orders() {
    let mut count = 0;
    for mask in 0..256u32 {
        for shift in [0,4,8] {
            let mut bits: Vec<u32> = (0..8).filter(|&b| mask & (1 << b) != 0)
                .map(|b| b + shift).collect();
            check(&bits);
            bits.reverse();
            check(&bits);
            if !bits.is_empty() { bits.rotate_left(1); }
            check(&bits);
            count += 3;
        }
    }
    assert_eq!(count, 2304);
}

#[test]
fn full_width_and_empty() {
    check(&[]);
    check(&(0..16).collect::<Vec<u32>>());
    check(&(0..16).rev().collect::<Vec<u32>>());
}
"""


class TextureSpreadReview(unittest.TestCase):
    def test_append_only(self):
        source = OLD.encode()
        fixture = FIXTURE.read_bytes()
        result = preview(source, fixture, blob(source))
        self.assertTrue(result.startswith(source))
        self.assertIn(NEW.encode(), result[len(source):])
        self.assertEqual(result.count(b"#[cfg(test)]"), 2)

    def test_pin_and_anchor_refusals(self):
        source = OLD.encode()
        fixture = FIXTURE.read_bytes()
        with self.assertRaises(ValueError):
            preview(source, fixture)
        for changed in (source + source, b"fn other() {}", source + b"spread_incremental"):
            with self.subTest(length=len(changed)), self.assertRaises(ValueError):
                preview(changed, fixture, blob(changed))
        with self.assertRaises(ValueError):
            preview(source, b"bad fixture", blob(source))

    def test_portable_exact_functions(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "spread.rs"
            exe = Path(tmp) / "spread"
            src.write_text(OLD + "\n" + NEW + "\n" + AXES + RUST_TESTS)
            subprocess.run([rustc, "--edition=2021", "--test", str(src), "-o", str(exe)],
                           check=True, timeout=90)
            subprocess.run([str(exe)], check=True, timeout=30)


if __name__ == "__main__":
    unittest.main()
