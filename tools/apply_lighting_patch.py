#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional correctness-first shader page-boundary experiment."""
import argparse
from pathlib import Path
import sys

from apply_memory_patch import blob_hash

SOURCE = "crates/victory-shader/src/emit/lower.rs"
EXPECTED = "600139ae89213d68ea4256d01c5b435e030b0c49"
EDITS = [["            let (h, byte) = self.memory(lo, hi, guard);\n            let mask = self.s.m.i8((1u8 << n) - 1);\n            let r = self.s.op(\n                c,\n                \"rawBufferLoad.f32\",\n                Attr::ReadOnly,\n                res,\n                139,\n                &[h, byte, iu, mask, align],\n            );\n            for k in 0..n {\n                let x = self.s.m.extract(c, r, u32::from(k));\n                let x = self.as_int(x);\n                self.write(inst, Reg::V(reg + k), x, guard);\n            }\n","            // A vector can cross into another 64 KiB directory page.\n            // Resolve each aligned dword rather than extending the first view.\n            for k in 0..n {\n                let (word_lo, word_hi) = self.address_plus(lo, hi, 4 * i32::from(k));\n                let (h, byte) = self.memory(word_lo, word_hi, guard);\n                let mask = self.s.m.i8(1);\n                let r = self.s.op(\n                    c,\n                    \"rawBufferLoad.f32\",\n                    Attr::ReadOnly,\n                    res,\n                    139,\n                    &[h, byte, iu, mask, align],\n                );\n                let x = self.s.m.extract(c, r, 0);\n                let x = self.as_int(x);\n                self.write(inst, Reg::V(reg + k), x, guard);\n            }\n"],["            let (h, byte) = self.memory(lo, hi, guard);\n            let mut args = vec![h, byte, iu];\n            args.extend(&vals);\n            args.resize(3 + 4, iu);\n            args.push(self.s.m.i8((1u8 << n) - 1));\n            args.push(align);\n            let at = self.begin_guarded(guard);\n            self.s\n                .op(self.cur, \"rawBufferStore.i32\", Attr::NoUnwind, void, 140, &args);\n            self.end_guarded(at, &[]);\n","            // Resolve all words before entering the guarded store block.\n            let mut locations = Vec::with_capacity(usize::from(n));\n            for k in 0..n {\n                let (word_lo, word_hi) = self.address_plus(lo, hi, 4 * i32::from(k));\n                locations.push(self.memory(word_lo, word_hi, guard));\n            }\n            let mask = self.s.m.i8(1);\n            let at = self.begin_guarded(guard);\n            for ((h, byte), &value) in locations.into_iter().zip(vals.iter()) {\n                self.s.op(\n                    self.cur,\n                    \"rawBufferStore.i32\",\n                    Attr::NoUnwind,\n                    void,\n                    140,\n                    &[h, byte, iu, value, iu, iu, iu, mask, align],\n                );\n            }\n            self.end_guarded(at, &[]);\n"],["        for first in (0..count).step_by(4) {\n            let n = (count - first).min(4);\n            let (lo, hi) = self.address_plus(lo, hi, offset + 4 * i32::from(first));\n            let (h, byte) = self.memory(lo, hi, None);\n            let mask = self.s.m.i8((1u8 << n) - 1);\n            let r = self.s.op(\n                c,\n                \"rawBufferLoad.f32\",\n                Attr::ReadOnly,\n                res,\n                139,\n                &[h, byte, iu, mask, align],\n            );\n            for k in 0..n {\n                let x = self.s.m.extract(c, r, u32::from(k));\n                let x = self.as_int(x);\n                self.write(inst, Reg::S(code + first + k), x, None);\n            }\n        }\n","        // Scalar vectors can also straddle a directory page boundary.\n        for k in 0..count {\n            let (word_lo, word_hi) = self.address_plus(lo, hi, offset + 4 * i32::from(k));\n            let (h, byte) = self.memory(word_lo, word_hi, None);\n            let mask = self.s.m.i8(1);\n            let r = self.s.op(\n                c,\n                \"rawBufferLoad.f32\",\n                Attr::ReadOnly,\n                res,\n                139,\n                &[h, byte, iu, mask, align],\n            );\n            let x = self.s.m.extract(c, r, 0);\n            let x = self.as_int(x);\n            self.write(inst, Reg::S(code + k), x, None);\n        }\n"]]

def patch_source(data):
    normalized = data.replace(b"\r\n", b"\n")
    if blob_hash(normalized) != EXPECTED:
        raise ValueError("Shader source revision differs from the reviewed blob.")
    result = normalized.decode("utf-8")
    for before, after in EDITS:
        if result.count(before) != 1:
            raise ValueError("Shader edit anchor differs.")
        result = result.replace(before, after)
    updated = result.encode("utf-8")
    return updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkout", type=Path)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    root = args.checkout.resolve()
    try:
        target = root / SOURCE
        if not (root / ".git").exists() or target.resolve() != target or not target.is_file():
            raise ValueError("Use a separate valid Git checkout.")
        updated = patch_source(target.read_bytes())
        if args.apply:
            target.write_bytes(updated)
            print("Experimental per-dword shader access candidate applied.")
        else:
            print("Shader source validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
