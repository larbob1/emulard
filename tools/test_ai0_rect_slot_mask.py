# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable exact slot-enumeration blocks with synthetic pipeline inputs."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from preview_ai0_rect_slot_mask import START, END, OLD, NEW, blob, clone, preview


class RectSlotMaskReview(unittest.TestCase):
    def source(self):
        return (START + "\n" + OLD + "            // unchanged body\n        }\n" + END + ") {}\n").encode()

    def test_append_only_and_exact_substitution(self):
        data = self.source()
        result = preview(data, blob(data))
        self.assertTrue(result.startswith(data))
        generated = clone(data.decode())
        self.assertIn(NEW, generated)
        self.assertNotIn(OLD, generated)
        self.assertIn("// unchanged body", generated)
        self.assertEqual(result.count(b"#[cfg(test)]"), 1)

    def test_refuse_wrong_pin_or_drift(self):
        data = self.source()
        with self.assertRaises(ValueError):
            preview(data)
        for changed in (data + data, data.replace(OLD.encode(), b"// drift\n"),
                        data + b"rectangles_active_slots"):
            with self.assertRaises(ValueError):
                preview(changed, blob(changed))

    def test_portable_exact_enumeration(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required")
        prefix = """
#[derive(Clone, Copy)]
struct Input { slot: u32, offset: u32, format: u32, per_instance: bool }
struct Pipeline { inputs: Vec<Input> }
type Groups = Vec<(u32, Vec<(u32,u32)>)>;
"""
        def function(name, block):
            return (
                "fn " + name + "(p: &Pipeline, fail: Option<u32>) -> (bool, Groups) {\n"
                "let mut seen = Vec::new();\n" + block +
                "seen.push((slot,elements));\n"
                "if fail == Some(slot) { return (false,seen); }\n"
                "}\n(true,seen)\n}\n"
            )
        cases = """
fn input(slot: u32, ordinal: u32, per_instance: bool) -> Input {
    Input { slot, offset: ordinal, format: ordinal%13, per_instance }
}

fn oracle(p: &Pipeline, fail: Option<u32>) -> (bool, Groups) {
    let mut by_slot = std::collections::BTreeMap::new();
    for e in &p.inputs {
        if !e.per_instance && e.slot < 32 {
            by_slot.entry(e.slot).or_insert_with(Vec::new).push((e.offset,e.format));
        }
    }
    let mut seen = Vec::new();
    for (slot, entries) in by_slot {
        seen.push((slot,entries));
        if fail == Some(slot) { return (false,seen); }
    }
    (true,seen)
}

fn verify(p: &Pipeline) {
    for fail in std::iter::once(None).chain((0..=32).map(Some)) {
        let expected = oracle(p,fail);
        assert_eq!(baseline(p,fail),expected);
        assert_eq!(candidate(p,fail),expected);
    }
}

#[test]
fn every_small_slot_subset_and_order() {
    let slots = [0,1,3,7,15,23,30,31];
    for mask in 0..256u32 {
        let mut entries = vec![input(32,999,false),input(u32::MAX,998,false)];
        for (i,&slot) in slots.iter().enumerate() {
            entries.push(input(slot,100+i as u32,true));
            if mask & (1<<i) != 0 {
                entries.push(input(slot,2*i as u32,false));
                entries.push(input(slot,2*i as u32+1,false));
            }
        }
        verify(&Pipeline{inputs:entries.clone()});
        entries.reverse();
        verify(&Pipeline{inputs:entries});
    }
}

#[test]
fn empty_dense_duplicates_and_invalid_inputs() {
    verify(&Pipeline{inputs:vec![]});
    verify(&Pipeline{inputs:vec![input(32,0,false),input(u32::MAX,1,false)]});
    verify(&Pipeline{inputs:(0..32).rev().map(|s| input(s,s,false)).collect()});
    verify(&Pipeline{inputs:(0..64).map(|i| input(31,i,i%3==0)).collect()});
}

#[test]
fn full_scan_work_model() {
    for n in [0usize,1,32,128] {
        for active in 0..=32 {
            let original = 32*n;
            let proposed = (1+active)*n;
            if active < 31 && n != 0 { assert!(proposed < original); }
            if active == 31 { assert_eq!(proposed,original); }
            if active == 32 { assert_eq!(proposed,original+n); }
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "slot.rs"
            exe = Path(tmp) / "slot"
            src.write_text(prefix + function("baseline", OLD) + function("candidate", NEW) + cases)
            subprocess.run([rustc, "--edition=2021", "--test", str(src), "-o", str(exe)],
                           check=True, timeout=90)
            subprocess.run([str(exe)], check=True, timeout=30)


if __name__ == "__main__":
    unittest.main()
