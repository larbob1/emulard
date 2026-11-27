# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute exact prepared scalar-memory lowering with synthetic IR/view stubs.

The directory resolver is a model, not actual GPU memory or DXIL execution.
The address_plus fixture is copied verbatim from pinned upstream.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES

STUBS = r'''// Minimal executable IR/host-view stub. Values represent u32 SSA numbers
// except the synthetic load result, which encodes a directory page+offset.
// Distinct page mappings deliberately cannot be read through another page.
type V = u64;
type Why = &'static str;
const NULL: u8 = 125;
#[derive(Clone,Copy)]
enum Operand { Scalar { code: u8 } }
#[derive(Clone,Copy)]
enum Fields { Smem { data: Option<Operand>, base: Operand, offset: i32, soffset: Operand }, Other }
#[derive(Clone,Copy)]
enum Reg { S(u8) }
struct Inst { fields: Fields, name: &'static str, regs: [u32; 128] }
impl Inst {
    fn name(&self) -> &'static str { self.name }
    fn read(&self, reg: Reg) -> Option<V> { let Reg::S(k) = reg; self.regs.get(k as usize).map(|&v| v as V) }
}
enum Bin { Add, Sub }
enum Cast { ZExt }
enum Attr { ReadOnly }
mod pred { pub const IULT: u8 = 0; pub const IUGT: u8 = 1; }
struct Module;
fn word(page: u64, byte: u64) -> V {
    // page 2 is unmapped; a read beyond the selected 64KiB view is zero.
    if page == 2 || byte >= 65536 { 0 }
    else { ((page.wrapping_mul(0x9e37) ^ byte) as u32) as V }
}
impl Module {
    fn i32(&mut self, v: u32) -> V { v as V }
    fn i8(&mut self, v: u8) -> V { v as V }
    fn undef(&mut self, _: u32) -> V { 0 }
    fn bin(&mut self, _: usize, op: Bin, a: V, b: V) -> V {
        (match op { Bin::Add => (a as u32).wrapping_add(b as u32), Bin::Sub => (a as u32).wrapping_sub(b as u32) }) as V
    }
    fn cmp(&mut self, _: usize, op: u8, a: V, b: V) -> V {
        u64::from(if op == pred::IULT { a < b } else { a > b })
    }
    fn cast(&mut self, _: usize, _: Cast, v: V, _: u32) -> V { v }
    fn extract(&mut self, _: usize, r: V, k: u32) -> V { word(r >> 16, (r & 65535) + 4*u64::from(k)) }
}
struct Types { i32: u32, res_ret: u32 }
struct Shader { m: Module, t: Types, calls: Vec<(V,V,V)> }
impl Shader {
    fn op(&mut self, _: usize, name: &str, _: Attr, _: u32, opcode: u32, args: &[V]) -> V {
        assert_eq!((name, opcode, args.len(), args[4]), ("rawBufferLoad.f32", 139, 5, 4));
        self.calls.push((args[0], args[1], args[3]));
        args[0] << 16 | args[1]
    }
}
struct Lower { s: Shader, cur: usize, written: Vec<(u8,V)>, lookups: Vec<(V,V)> }
impl Lower {
    fn new() -> Self { Self { s: Shader { m: Module, t: Types { i32: 0, res_ret: 0 }, calls: vec![] }, cur: 0, written: vec![], lookups: vec![] } }
    fn i32_of(&mut self, v: V) -> Result<V,Why> { Ok(v) }
    fn operand(&mut self, inst: &Inst, operand: &Operand) -> Result<V,Why> {
        let Operand::Scalar { code } = *operand;
        inst.read(Reg::S(code)).ok_or("operand")
    }
    fn memory(&mut self, lo: V, hi: V, guard: Option<V>) -> (V,V) {
        assert!(guard.is_none());
        self.lookups.push((lo,hi));
        ((lo >> 16) | ((hi & 255) << 16), lo & 65535)
    }
    fn as_int(&mut self, x: V) -> V { x }
    fn write(&mut self, _: &Inst, reg: Reg, value: V, guard: Option<V>) {
        assert!(guard.is_none());
        let Reg::S(k) = reg;
        self.written.push((k,value));
    }
'''
ADDRESS_PLUS = r'''    fn address_plus(&mut self, lo: V, hi: V, off: i32) -> (V, V) {
        if off == 0 {
            return (lo, hi);
        }
        let c = self.cur;
        let i32t = self.s.t.i32;
        let k = self.s.m.i32(off as u32);
        let sum = self.s.m.bin(c, Bin::Add, lo, k);
        // Up: a carry when the sum wrapped below `lo`. Down: a borrow when
        // it wrapped above.
        let wrapped = self
            .s
            .m
            .cmp(c, if off > 0 { pred::IULT } else { pred::IUGT }, sum, lo);
        let one = self.s.m.cast(c, Cast::ZExt, wrapped, i32t);
        let hi = self.s.m.bin(c, if off > 0 { Bin::Add } else { Bin::Sub }, hi, one);
        (sum, hi)
    }

'''
TESTS = r'''
}
#[cfg(test)]
mod tests {
    use super::*;
    fn enabled() -> bool { std::env::var_os("VICTORY_SCALAR_PAGE_LOADS").is_some_and(|v| v == "1") }
    fn run(name: &'static str, base: V, off: i32, dynamic: Option<u32>) -> (Lower, Result<(),Why>) {
        let mut regs = [0u32;128];
        regs[0] = base as u32; regs[1] = (base >> 32) as u32; regs[2] = dynamic.unwrap_or(0);
        let inst = Inst {
            name, regs, fields: Fields::Smem {
                data: Some(Operand::Scalar { code: 32 }), base: Operand::Scalar { code: 0 },
                offset: off, soffset: Operand::Scalar { code: if dynamic.is_some() { 2 } else { NULL } },
            },
        };
        let mut l = Lower::new();
        let result = l.memory_smem(&inst);
        (l,result)
    }
    fn expected(addr: V, n: u8) -> Vec<(u8,V)> {
        (0..n).map(|k| {
            let a = addr.wrapping_add(4*u64::from(k));
            (32+k, word((a>>16)&0xff_ffff,a&65535))
        }).collect()
    }
    #[test]
    fn every_supported_width_and_register_order() {
        for (name,n) in [("s_load_dword",1),("s_load_dwordx2",2),("s_load_dwordx4",4),("s_load_dwordx8",8),("s_load_dwordx16",16)] {
            let (l,r) = run(name,0x1234,0,None);
            assert_eq!(r,Ok(()));
            assert_eq!(l.written,expected(0x1234,n));
            let width = if enabled() {1} else {4};
            assert_eq!(l.lookups.len(),usize::from(n).div_ceil(width));
            for (i, &(_,_,mask)) in l.s.calls.iter().enumerate() {
                let remaining = usize::from(n)-i*width;
                assert_eq!(mask,(1u64<<remaining.min(width))-1);
            }
        }
    }
    #[test]
    fn crossing_distinct_directory_backings() {
        let (l,r) = run("s_load_dwordx4",65532,0,None);
        assert_eq!(r,Ok(()));
        if enabled() {
            assert_eq!(l.written,expected(65532,4));
            assert_eq!(l.s.calls,vec![(0,65532,1),(1,0,1),(1,4,1),(1,8,1)]);
        } else {
            assert_eq!(l.s.calls,vec![(0,65532,15)]);
            assert_eq!(l.written[1].1,0);
            assert_ne!(l.written,expected(65532,4));
        }
    }
    #[test]
    fn missing_page_and_following_mapped_page_resolved_independently() {
        let (l,r) = run("s_load_dwordx4",3*65536-4,0,None);
        assert_eq!(r,Ok(()));
        assert_eq!(l.written[0].1,0);
        if enabled() {
            assert_eq!(l.written,expected(3*65536-4,4));
            assert_eq!(l.s.calls[1].0,3);
            assert_ne!(l.written[1].1,0);
        } else {
            assert!(l.written.iter().all(|&(_,v)|v==0));
        }
    }
    #[test]
    fn low_word_carry_and_signed_immediate_preserved() {
        let (l,r) = run("s_load_dwordx4",0xffff_fffc, -4, Some(4));
        assert_eq!(r,Ok(()));
        if enabled() {
            assert_eq!(l.lookups,vec![(0xffff_fffc,0),(0,1),(4,1),(8,1)]);
            assert_eq!(l.written,expected(0xffff_fffc,4));
        } else { assert_eq!(l.lookups,vec![(0xffff_fffc,0)]); }
        let (l,r) = run("s_load_dword",0xffff_fffc, -4, Some(8));
        assert_eq!(r,Ok(()));
        assert_eq!(l.lookups,vec![(0,1)]);
    }
    #[test]
    fn unsupported_memory_ops_remain_refused_before_lookups() {
        for name in ["s_store_dword","s_atomic_add","s_load_dwordx3","s_buffer_load_dword"] {
            let (l,r) = run(name,0,0,None);
            assert_eq!(r,Err("a scalar memory access by address"));
            assert!(l.lookups.is_empty());
            assert!(l.written.is_empty());
        }
    }
}
'''


class ScalarPageLoadTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "rustc required")
    def test_actual_scalar_lowering(self):
        body, = [new for old, new in PATCHES["crates/victory-shader/src/emit/lower.rs"]
                 if old.startswith("    fn memory_smem(")]
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "scalar.rs"
            binary = root / "scalar-tests.exe"
            source.write_text(STUBS + ADDRESS_PLUS + body + TESTS, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            for value in ["0", "1"]:
                with self.subTest(value=value):
                    result = subprocess.run([str(binary)], env=dict(os.environ, VICTORY_SCALAR_PAGE_LOADS=value),
                                            check=True, capture_output=True, text=True, timeout=30)
                    self.assertIn("5 passed; 0 failed", result.stdout)
