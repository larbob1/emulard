#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional collision-free GPU fault reporting experiment."""
import argparse
from pathlib import Path
import subprocess
import sys
from apply_memory_patch import blob_hash, patch_source as memory_patch
from apply_lighting_patch import patch_source as lighting_patch

SPECS = [["crates/victory-gpu/src/memory.rs","c25636783511fdfbf9692fdd36ef150f69ea666e",[["        for i in 1..MEMORY_FAULTS as usize {\n            // SAFETY: inside the faults' mapping; the GPU may be writing,\n            // a number missed now is written again next frame.\n            let at = unsafe { self.faults.1.add(i) };\n            // SAFETY: as above.\n            let page = unsafe { at.read_volatile() };\n            if page != 0 {\n                pages.push(page);\n                // SAFETY: as above.\n                unsafe { at.write_volatile(0) };\n            }\n        }\n","        for i in 0..MEMORY_FAULTS as usize {\n            // SAFETY: inside the mapped fault buffer.\n            let at = unsafe { self.faults.1.add(i) };\n            let bits = unsafe { at.read_volatile() };\n            if bits != 0 {\n                // As with the original reporting path, a concurrent GPU\n                // update can race this clear. A later access can report again.\n                unsafe { at.write_volatile(0) };\n                pages.extend(fault_pages(i as u32, bits));\n            }\n        }\n"],["impl Memory {\n","/// Decode the set bits for one word, excluding the reserved final page.\nfn fault_pages(word: u32, mut bits: u32) -> impl Iterator<Item = u32> {\n    std::iter::from_fn(move || {\n        while bits != 0 {\n            let bit = bits.trailing_zeros();\n            bits &= bits - 1;\n            let page = word * 32 + bit;\n            if page < MEMORY_PAGES - 1 {\n                return Some(page);\n            }\n        }\n        None\n    })\n}\n\n#[cfg(test)]\nmod fault_bitmap_tests {\n    use super::{fault_pages, MEMORY_PAGES};\n\n    #[test]\n    fn each_missing_page_is_retained() {\n        assert_eq!(fault_pages(0, 0x8000_0003).collect::<Vec<_>>(), vec![0, 1, 31]);\n        assert_eq!(fault_pages(1, 1).collect::<Vec<_>>(), vec![32]);\n        assert!(fault_pages(2, 0).next().is_none());\n    }\n\n    #[test]\n    fn reserved_page_is_not_mapped() {\n        assert_eq!(fault_pages(MEMORY_PAGES / 32 - 1, 0xC000_0000).collect::<Vec<_>>(),\n                   vec![MEMORY_PAGES - 2]);\n    }\n}\n\nimpl Memory {\n"]]],["crates/victory-shader/src/emit/lower.rs","600139ae89213d68ea4256d01c5b435e030b0c49",[["        let places = k(self, MEMORY_FAULTS - 1);\n        let place = self.s.m.bin(c, Bin::URem, page, places);\n        let one = k(self, 1);\n        let place = self.s.m.bin(c, Bin::Add, place, one);\n        let k2 = k(self, 2);\n        let place = self.s.m.bin(c, Bin::Shl, place, k2);\n        let place = self.s.m.select(c, missing, place, zero);\n        let faults = self.s.root_uav_handle(SLOT_FAULTS);\n        let void = self.s.t.void;\n        let mask = self.s.m.i8(1);\n        self.s.op(\n            c,\n            \"rawBufferStore.i32\",\n            Attr::NoUnwind,\n            void,\n            140,\n            &[faults, place, iu, page, iu, iu, iu, mask, align],\n        );\n","        // Every directory page has its own bit. Atomic OR preserves\n        // simultaneous reports for different pages in the same word.\n        let k5 = k(self, 5);\n        let k31 = k(self, 31);\n        let k2 = k(self, 2);\n        let word = self.s.m.bin(c, Bin::LShr, page, k5);\n        let place = self.s.m.bin(c, Bin::Shl, word, k2);\n        let bit = self.s.m.bin(c, Bin::And, page, k31);\n        let one = k(self, 1);\n        let bit = self.s.m.bin(c, Bin::Shl, one, bit);\n        let report = self.s.m.select(c, missing, bit, zero);\n        let faults = self.s.root_uav_handle(SLOT_FAULTS);\n        let or_op = k(self, 2);\n        self.s.op(\n            c,\n            \"atomicBinOp.i32\",\n            Attr::NoUnwind,\n            i32t,\n            78,\n            &[faults, or_op, place, iu, iu, report],\n        );\n"],["{MEMORY_FAULTS, MEMORY_PAGES, SLOT_FAULTS, SLOT_MEMORY, USER_MEMORY_BASE}","{MEMORY_PAGES, SLOT_FAULTS, SLOT_MEMORY, USER_MEMORY_BASE}"]]],["crates/victory-shader/src/emit/shader.rs","b49bc6def69b7d91d8a90d9fe4d5df6daebe4678",[["/// - the root UAV `u<SLOT_FAULTS>` takes the page numbers of accesses that\n///   found no copy ([`MEMORY_FAULTS`] dwords, dword 0 a sink), which the\n///   host reads afterwards to make those copies for the frames to come.","/// - the root UAV `u<SLOT_FAULTS>` holds one fault bit per directory page;\n///   the host reads the bitmap to prepare missing copies for later frames."],["pub const MEMORY_FAULTS: u32 = 4096;","pub const MEMORY_FAULTS: u32 = MEMORY_PAGES.div_ceil(32);"]]]]

def normalize(data):
    return data.replace(b"\r\n", b"\n")

def transform(data, edits):
    source = normalize(data).decode("utf-8")
    for before, after in edits:
        if source.count(before) != 1:
            raise ValueError("Fault bitmap anchor differs.")
        source = source.replace(before, after)
    updated = source.encode("utf-8")
    return updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.checkout.resolve()
    try:
        if not (root / ".git").exists():
            raise ValueError("Separate Git checkout required.")
        pending = {}
        for path, expected, edits in SPECS:
            target = root / path
            if target.resolve() != target or not target.is_file():
                raise ValueError("Invalid source path.")
            original = subprocess.check_output(["git", "show", "HEAD:" + path], cwd=root)
            if blob_hash(normalize(original)) != expected:
                raise ValueError("Pinned source differs.")
            if path == SPECS[0][0]:
                predecessor = memory_patch(path, original)
            elif path == SPECS[1][0]:
                predecessor = lighting_patch(original)
            else:
                predecessor = original
            current = target.read_bytes()
            if normalize(current) != normalize(predecessor):
                raise ValueError("Apply the reviewed memory and lighting candidates first.")
            pending[target] = transform(current, edits)
        if args.apply:
            for target, data in pending.items():
                target.write_bytes(data)
            print("Experimental fault bitmap applied.")
        else:
            print("Fault bitmap source checks passed; dry run only.")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("Fault bitmap preparation failed.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
