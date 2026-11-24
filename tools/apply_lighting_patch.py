#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional correctness-first shader page-boundary experiment."""
import argparse
from pathlib import Path
import sys

from apply_memory_patch import blob_hash

SOURCE = "crates/victory-shader/src/emit/lower.rs"
EXPECTED = "600139ae89213d68ea4256d01c5b435e030b0c49"
SCALAR_EDITS = [["        if *lds || !matches!(saddr, None | Some(Operand::Scalar { code: NULL, .. })) {\n            return Err(\"a global address with a scalar base\");\n        }\n        let Some(Operand::Vector { reg: areg, .. }) = *addr else {\n            return Err(\"a global address not in VGPRs\");\n        };\n        let word = |l: &mut Self, k: u8| -> Result<V, Why> {\n            let v = inst.read(Reg::V(areg + k)).ok_or(\"a global address\")?;\n            l.i32_of(v)\n        };\n        let (lo, hi) = (word(self, 0)?, word(self, 1)?);\n","        if *lds {\n            return Err(\"a global address using LDS\");\n        }\n        let Some(Operand::Vector { reg: areg, .. }) = *addr else {\n            return Err(\"a global address not in VGPRs\");\n        };\n        let read = |l: &mut Self, r: Reg| -> Result<V, Why> {\n            let value = inst.read(r).ok_or(\"a global address\")?;\n            l.i32_of(value)\n        };\n        // The scalar-base form has one unsigned per-lane byte offset.\n        // Preserve its carry into the high address word before applying\n        // the existing signed instruction displacement.\n        let (lo, hi) = match *saddr {\n            Some(Operand::Scalar { code, .. }) if code != NULL => {\n                let lo = read(self, Reg::S(code))?;\n                let hi = read(self, Reg::S(code + 1))?;\n                let displacement = read(self, Reg::V(areg))?;\n                let block = self.cur;\n                let sum = self.s.m.bin(block, Bin::Add, lo, displacement);\n                let carry = self.s.m.cmp(block, pred::IULT, sum, lo);\n                let carry = self.s.m.cast(block, Cast::ZExt, carry, self.s.t.i32);\n                let upper = self.s.m.bin(block, Bin::Add, hi, carry);\n                (sum, upper)\n            }\n            None | Some(Operand::Scalar { code: NULL, .. }) => {\n                (read(self, Reg::V(areg))?, read(self, Reg::V(areg + 1))?)\n            }\n            _ => return Err(\"an unsupported global scalar address operand\"),\n        };\n"],["    #[test]\n    fn buffer_cache_invalidations_lower_as_no_ops()","    #[test]\n    fn raw_scalar_base_global_access_lowers() {\n        // Synthetic scalar base 0x00000000_ffffffff and offset 1;\n        // the store keeps the loaded value live. No external data.\n        let words = [\n            0xBE80_03C1, // s_mov_b32 s0, -1\n            0xBE81_0380, // s_mov_b32 s1, 0\n            0x7E02_0281, // v_mov_b32 v1, 1\n            0xDC30_8000, 0x0200_0001, // global_load_dword v2, v1, s[0:1]\n            0xBF8C_0000, // s_waitcnt\n            0xDC70_8004, 0x0000_0201, // global_store_dword v1, v2, s[0:1] offset:4\n            S_ENDPGM,\n        ];\n        assert!(lowers(&words, 0).is_ok());\n    }\n\n    #[test]\n    fn buffer_cache_invalidations_lower_as_no_ops()"]]
EDITS = [["            let (h, byte) = self.memory(lo, hi, guard);\n            let mask = self.s.m.i8((1u8 << n) - 1);\n            let r = self.s.op(\n                c,\n                \"rawBufferLoad.f32\",\n                Attr::ReadOnly,\n                res,\n                139,\n                &[h, byte, iu, mask, align],\n            );\n            for k in 0..n {\n                let x = self.s.m.extract(c, r, u32::from(k));\n                let x = self.as_int(x);\n                self.write(inst, Reg::V(reg + k), x, guard);\n            }\n","            // A vector can cross into another 64 KiB directory page.\n            // Resolve each aligned dword rather than extending the first view.\n            for k in 0..n {\n                let (word_lo, word_hi) = self.address_plus(lo, hi, 4 * i32::from(k));\n                let (h, byte) = self.memory(word_lo, word_hi, guard);\n                let mask = self.s.m.i8(1);\n                let r = self.s.op(\n                    c,\n                    \"rawBufferLoad.f32\",\n                    Attr::ReadOnly,\n                    res,\n                    139,\n                    &[h, byte, iu, mask, align],\n                );\n                let x = self.s.m.extract(c, r, 0);\n                let x = self.as_int(x);\n                self.write(inst, Reg::V(reg + k), x, guard);\n            }\n"],["            let (h, byte) = self.memory(lo, hi, guard);\n            let mut args = vec![h, byte, iu];\n            args.extend(&vals);\n            args.resize(3 + 4, iu);\n            args.push(self.s.m.i8((1u8 << n) - 1));\n            args.push(align);\n            let at = self.begin_guarded(guard);\n            self.s\n                .op(self.cur, \"rawBufferStore.i32\", Attr::NoUnwind, void, 140, &args);\n            self.end_guarded(at, &[]);\n","            // Resolve all words before entering the guarded store block.\n            let mut locations = Vec::with_capacity(usize::from(n));\n            for k in 0..n {\n                let (word_lo, word_hi) = self.address_plus(lo, hi, 4 * i32::from(k));\n                locations.push(self.memory(word_lo, word_hi, guard));\n            }\n            let mask = self.s.m.i8(1);\n            let at = self.begin_guarded(guard);\n            for ((h, byte), &value) in locations.into_iter().zip(vals.iter()) {\n                self.s.op(\n                    self.cur,\n                    \"rawBufferStore.i32\",\n                    Attr::NoUnwind,\n                    void,\n                    140,\n                    &[h, byte, iu, value, iu, iu, iu, mask, align],\n                );\n            }\n            self.end_guarded(at, &[]);\n"],["        for first in (0..count).step_by(4) {\n            let n = (count - first).min(4);\n            let (lo, hi) = self.address_plus(lo, hi, offset + 4 * i32::from(first));\n            let (h, byte) = self.memory(lo, hi, None);\n            let mask = self.s.m.i8((1u8 << n) - 1);\n            let r = self.s.op(\n                c,\n                \"rawBufferLoad.f32\",\n                Attr::ReadOnly,\n                res,\n                139,\n                &[h, byte, iu, mask, align],\n            );\n            for k in 0..n {\n                let x = self.s.m.extract(c, r, u32::from(k));\n                let x = self.as_int(x);\n                self.write(inst, Reg::S(code + first + k), x, None);\n            }\n        }\n","        // Scalar vectors can also straddle a directory page boundary.\n        for k in 0..count {\n            let (word_lo, word_hi) = self.address_plus(lo, hi, offset + 4 * i32::from(k));\n            let (h, byte) = self.memory(word_lo, word_hi, None);\n            let mask = self.s.m.i8(1);\n            let r = self.s.op(\n                c,\n                \"rawBufferLoad.f32\",\n                Attr::ReadOnly,\n                res,\n                139,\n                &[h, byte, iu, mask, align],\n            );\n            let x = self.s.m.extract(c, r, 0);\n            let x = self.as_int(x);\n            self.write(inst, Reg::S(code + k), x, None);\n        }\n"]]
EDITS = SCALAR_EDITS + EDITS

def patch_source(data, scalar_only=False):
    normalized = data.replace(b"\r\n", b"\n")
    if blob_hash(normalized) != EXPECTED:
        raise ValueError("Shader source revision differs from the reviewed blob.")
    result = normalized.decode("utf-8")
    for before, after in (SCALAR_EDITS if scalar_only else EDITS):
        if result.count(before) != 1:
            raise ValueError("Shader edit anchor differs.")
        result = result.replace(before, after)
    updated = result.encode("utf-8")
    return updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkout", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--scalar-only", action="store_true", help="apply only raw scalar-base address support")
    args = ap.parse_args()
    root = args.checkout.resolve()
    try:
        target = root / SOURCE
        if not (root / ".git").exists() or target.resolve() != target or not target.is_file():
            raise ValueError("Use a separate valid Git checkout.")
        updated = patch_source(target.read_bytes(), scalar_only=args.scalar_only)
        if args.apply:
            target.write_bytes(updated)
            print("Shader address candidate applied.")
        else:
            print("Shader source validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
