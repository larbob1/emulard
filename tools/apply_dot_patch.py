#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add packed-byte dot-product lowering to reviewed source candidates."""
import argparse
from pathlib import Path
import subprocess
import sys
from apply_memory_patch import blob_hash
from apply_lighting_patch import patch_source as lighting_patch
from apply_fault_bitmap import SPECS as FEEDBACK_SPECS, transform as feedback_patch

SPECS = [["crates/victory-shader/src/emit/lower.rs","600139ae89213d68ea4256d01c5b435e030b0c49",[["            \"v_mad_u64_u32\" => {","            \"v_dot4_i32_i8\" | \"v_dot4_u32_u8\" => {\n                if v.clamp || v.neg != 0 || v.neg_hi != 0 || v.abs != 0\n                    || v.omod != 0 || v.sdwa.is_some() || v.dpp.is_some()\n                {\n                    return Err(\"modifiers on a packed byte dot product\");\n                }\n                let signed = name == \"v_dot4_i32_i8\";\n                let mut packed = Vec::with_capacity(2);\n                for k in 0..2 {\n                    let x = s(self, k)?;\n                    let lo_high = v.opsel & (1 << k) != 0;\n                    let hi_high = v.opsel_hi & (1 << k) != 0;\n                    let shift = self.s.m.i32(16);\n                    let mask = self.s.m.i32(0xffff);\n                    let lo = self.s.m.bin(c, Bin::And, x, mask);\n                    let hi = self.s.m.bin(c, Bin::LShr, x, shift);\n                    let upper = self.s.m.bin(c, Bin::Shl, if hi_high { hi } else { lo }, shift);\n                    packed.push(self.s.m.bin(c, Bin::Or, if lo_high { hi } else { lo }, upper));\n                }\n                let mut total = s(self, 2)?;\n                for k in 0..4u32 {\n                    let shift = self.s.m.i32(8 * k);\n                    let mask = self.s.m.i32(255);\n                    let extend = |l: &mut Self, x: V| {\n                        let x = l.s.m.bin(c, Bin::LShr, x, shift);\n                        if signed {\n                            let shift24 = l.s.m.i32(24);\n                            let x = l.s.m.bin(c, Bin::Shl, x, shift24);\n                            l.s.m.bin(c, Bin::AShr, x, shift24)\n                        } else {\n                            l.s.m.bin(c, Bin::And, x, mask)\n                        }\n                    };\n                    let a = extend(self, packed[0]);\n                    let b = extend(self, packed[1]);\n                    let product = self.s.m.bin(c, Bin::Mul, a, b);\n                    total = self.s.m.bin(c, Bin::Add, total, product);\n                }\n                int(self, total)\n            }\n            \"v_mad_u64_u32\" => {"]]],["crates/victory-shader/src/emit/valu_tests.rs","5072d6c513e669a22e06df07ca745c1ccd3f2930",[["#[test]\nfn packed_add_selects_halves_of_inline_constants()","fn dot4_words(signed: bool, duplicate_high: bool) -> [u32; 2] {\n    let op = if signed { 0x16 } else { 0x17 };\n    [0x33 << 26 | op << 16 | 1 << 14 | (duplicate_high as u32) << 11,\n     3 << 27 | u32::from(vgpr(1)) | u32::from(vgpr(2)) << 9 | u32::from(vgpr(3)) << 18]\n}\n\nfn dot4_reference(a: u32, b: u32, acc: u32, signed: bool, duplicate_high: bool) -> u32 {\n    let a = if duplicate_high { (a >> 16) | (a & 0xffff0000) } else { a };\n    let lane = |word: u32, i: u32| {\n        let byte = (word >> (i * 8)) as u8;\n        if signed { i32::from(byte as i8) } else { i32::from(byte) }\n    };\n    (0..4).fold(acc, |sum, i| sum.wrapping_add((lane(a, i) * lane(b, i)) as u32))\n}\n\n#[test]\nfn packed_byte_dot_lowering() {\n    for signed in [false, true] {\n        for duplicate in [false, true] {\n            let shader = build_valu_cs(&dot4_words(signed, duplicate));\n            assert!(!shader.dxil.is_empty());\n        }\n    }\n    assert_eq!(dot4_reference(0xffffffff, 0x01010101, 0, true, false), 0xfffffffc);\n    assert_eq!(dot4_reference(0xffffffff, 0x01010101, 0, false, false), 1020);\n    assert_eq!(dot4_reference(0x01010101, 0x01010101, u32::MAX, false, false), 3);\n    assert_eq!(dot4_reference(0x01020304, 0x01010101, 0, true, true), 6);\n}\n\n#[test]\nfn packed_byte_dot_gpu_reference() {\n    let cases = [\n        [0xffffffff, 0x01010101, 0, 0],\n        [0x807fff01, 0xff807f02, 0xfffffff0, 0],\n        [0x01020304, 0x01010101, 0, 0],\n        [0x01010101, 0x01010101, u32::MAX, 0],\n        [0, 0xffffffff, 123, 0],\n    ];\n    for signed in [false, true] {\n        for duplicate in [false, true] {\n            let shader = build_valu_cs(&dot4_words(signed, duplicate));\n            run_cases(&shader, &cases, |backend, _, input, got| {\n                assert_eq!(got, dot4_reference(input[0], input[1], input[2], signed, duplicate),\n                           \"{backend}: packed byte dot {input:x?}\");\n            });\n        }\n    }\n}\n\n#[test]\nfn packed_add_selects_halves_of_inline_constants()"]]]]

def normalized(data):
    return data.replace(b"\r\n", b"\n")

def transform(data, edits):
    source = normalized(data).decode("utf-8")
    for before, after in edits:
        if source.count(before) != 1:
            raise ValueError("Packed-dot anchor differs.")
        source = source.replace(before, after)
    result = source.encode("utf-8")
    return result.replace(b"\n", b"\r\n") if b"\r\n" in data else result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--lighting-memory", action="store_true")
    args = parser.parse_args()
    root = args.checkout.resolve()
    try:
        if not (root / ".git").exists():
            raise ValueError("Separate checkout required.")
        pending = {}
        for path, expected, edits in SPECS:
            target = root / path
            if target.resolve() != target or not target.is_file():
                raise ValueError("Invalid path.")
            original = subprocess.check_output(["git", "show", "HEAD:" + path], cwd=root)
            if blob_hash(normalized(original)) != expected:
                raise ValueError("Unexpected pinned blob.")
            predecessor = original
            if path == SPECS[0][0]:
                predecessor = lighting_patch(original, scalar_only=not args.lighting_memory)
                if args.lighting_memory:
                    feedback_edits = next(e for p, _, e in FEEDBACK_SPECS if p == path)
                    predecessor = feedback_patch(predecessor, feedback_edits)
            current = target.read_bytes()
            if normalized(current) != normalized(predecessor):
                raise ValueError("Unexpected predecessor source.")
            pending[target] = transform(current, edits)
        if args.apply:
            for target, data in pending.items():
                target.write_bytes(data)
        print("Packed-dot source checks passed.")
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Packed-dot preparation failed.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
