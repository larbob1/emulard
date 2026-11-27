# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable exact stage block with synchronous host recording seam."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from preview_ai0_root_constant_buffer import START, END, OLD, NEW, blob, clone, preview


class RootConstantBufferReview(unittest.TestCase):
    def source(self):
        return (START + "\n" + OLD + "        // unchanged tail\n" + END + "\n").encode()

    def test_append_only(self):
        data = self.source()
        self.assertTrue(preview(data, blob(data)).startswith(data))
        candidate = clone(data.decode())
        self.assertIn(NEW, candidate)
        self.assertNotIn(OLD, candidate)
        self.assertIn("// unchanged tail", candidate)

    def test_refuse_drift(self):
        data = self.source()
        with self.assertRaises(ValueError):
            preview(data)
        for changed in (data+data, data.replace(OLD.encode(), b"// drift"), data+b"bind_inline_constants"):
            with self.assertRaises(ValueError):
                preview(changed, blob(changed))

    def test_exact_block_parity(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required")
        prefix = """
#![allow(non_snake_case)]
use std::cell::RefCell;
#[derive(Clone,Copy,PartialEq,Eq)]
enum RootType { Table, Constants, Other(u32) }
struct User { root:RootType, slot:u8, index:u32, dword:u32 }
struct Host { user_data: Vec<User> }
struct Translated { host:Host }
struct Stage { user_data:Option<(u32,u32)> }
type Record=(bool,u32,u32,Vec<u32>);
struct List { records:RefCell<Vec<Record>> }
impl List {
    unsafe fn record(&self, compute:bool, param:u32, count:u32, ptr:*const u32, offset:u32) {
        let values=unsafe {std::slice::from_raw_parts(ptr,count as usize)}.to_vec();
        self.records.borrow_mut().push((compute,param,offset,values));
    }
    unsafe fn SetComputeRoot32BitConstants(&self,p:u32,n:u32,v:*const u32,o:u32) {
        unsafe {self.record(true,p,n,v,o)};
    }
    unsafe fn SetGraphicsRoot32BitConstants(&self,p:u32,n:u32,v:*const u32,o:u32) {
        unsafe {self.record(false,p,n,v,o)};
    }
}
struct State;
impl State {
    fn host_word(&self,compute:bool,kind:u32,slot:u8,dword:u32,memory:Option<&u32>)->u32 {
        kind+u32::from(slot)+dword+memory.copied().unwrap_or(0)+u32::from(compute)
    }
    fn user_value(&self,compute:bool,slot:u8,root:RootType,dword:u32)->u32 {
        u32::from(slot)*31+dword+u32::from(compute)+if root==RootType::Table {100} else {200}
    }
"""
        def function(name, block):
            return ("fn "+name+"(&self,l:&List,stage:&Stage,t:&Translated,made:&[(u8,u32)],"
                    "compute:bool,memory:Option<u32>) {\n"+block+"}\n")
        rust_tests = """
}
fn run(n:u32,mode:u32,compute:bool,mem:Option<u32>) {
    let stage=Stage{user_data:Some((mode,n))};
    let mut entries=Vec::new();
    if n>0 {
        for i in 0..n {
            if (i+mode)%5==0 {continue;}
            let root=match (i+mode)%3 {0=>RootType::Other(7),1=>RootType::Table,_=>RootType::Constants};
            entries.push(User{root,slot:(i%17) as u8,index:i,dword:i%11});
            if i%4==0 { entries.push(User{root:RootType::Other(9),slot:2,index:i,dword:3}); }
        }
        entries.push(User{root:RootType::Other(5),slot:0,index:n-1,dword:1});
    }
    let t=Translated{host:Host{user_data:entries}};
    let made=[(0,123),(0,456),(1,234),(16,987)];
    let a=List{records:RefCell::new(Vec::new())};
    let b=List{records:RefCell::new(Vec::new())};
    let mut expected=vec![0;n as usize];
    for u in &t.host.user_data {
        expected[u.index as usize]=match u.root {
            RootType::Other(k)=>State.host_word(compute,k,u.slot,u.dword,mem.as_ref()),
            RootType::Table=>made.iter().find(|m|m.0==u.slot).map(|m|m.1)
                .unwrap_or_else(||State.user_value(compute,u.slot,u.root,u.dword)),
            _=>State.user_value(compute,u.slot,u.root,u.dword),
        };
    }
    State.baseline(&a,&stage,&t,&made,compute,mem);
    State.candidate(&b,&stage,&t,&made,compute,mem);
    assert_eq!(*a.records.borrow(),vec![(compute,mode,0,expected.clone())]);
    assert_eq!(*b.records.borrow(),vec![(compute,mode,0,expected)]);
}
#[test]
fn sizes_and_stage_paths() {
    for n in (0..=65).chain([127,128,255,256]) {
        for mode in 0..8 {
            for compute in [false,true] {
                for mem in [None,Some(17)] {run(n,mode,compute,mem);}
            }
        }
    }
}
#[test]
fn absent_and_out_of_bounds() {
    let l=List{records:RefCell::new(Vec::new())};
    let t=Translated{host:Host{user_data:vec![User{root:RootType::Constants,slot:0,index:1,dword:0}]}};
    State.baseline(&l,&Stage{user_data:None},&t,&[],false,None);
    State.candidate(&l,&Stage{user_data:None},&t,&[],false,None);
    assert!(l.records.borrow().is_empty());
    for n in [0,1,64,65] {
        let bad=Translated{host:Host{user_data:vec![User{root:RootType::Constants,slot:0,index:n,dword:0}]}};
        let s=Stage{user_data:Some((0,n))};
        for candidate in [false,true] {
            let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                if candidate {State.candidate(&l,&s,&bad,&[],false,None)}
                else {State.baseline(&l,&s,&bad,&[],false,None)}
            }));
            assert!(result.is_err());
            assert!(l.records.borrow().is_empty());
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/"root.rs"
            exe = Path(tmp)/"root"
            src.write_text(prefix+function("baseline",OLD)+function("candidate",NEW)+rust_tests)
            subprocess.run([rustc,"--edition=2021","--test",str(src),"-o",str(exe)],check=True,timeout=90)
            subprocess.run([str(exe)],check=True,timeout=30)


if __name__ == "__main__":
    unittest.main()
