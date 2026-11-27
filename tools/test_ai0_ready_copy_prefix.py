# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare exact ready loop blocks using synthetic copies and list state."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from preview_ai0_ready_copy_prefix import START, OLD, NEW, blob, clone, preview


class ReadyCopyPrefixReview(unittest.TestCase):
    def source(self):
        return (START + ") {\n" + OLD + "    // unchanged return\n}\n").encode()

    def test_append_only(self):
        data = self.source()
        self.assertTrue(preview(data, blob(data)).startswith(data))
        candidate = clone(data.decode())
        self.assertIn(NEW, candidate)
        self.assertNotIn(OLD, candidate)
        self.assertIn("// unchanged return", candidate)

    def test_refuse_drift(self):
        data = self.source()
        with self.assertRaises(ValueError):
            preview(data)
        for changed in (data+data, data.replace(OLD.encode(), b"// drift"),
                        data+b"ready_skip_prefix"):
            with self.assertRaises(ValueError):
                preview(changed, blob(changed))

    def test_exact_loop_parity(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required")
        prefix = """
use std::cell::{Cell,RefCell};
use std::collections::HashSet;
#[derive(Debug,PartialEq,Eq)]
enum Event { First(usize), Refresh(usize,u64,u64), Write(usize,u64,u64), Keep(u32) }
#[derive(Default)]
struct List { seen:RefCell<HashSet<usize>>, events:RefCell<Vec<Event>> }
impl List {
    fn first_use(&self,k:usize)->bool {
        self.events.borrow_mut().push(Event::First(k));
        self.seen.borrow_mut().insert(k)
    }
    fn keep(&self,k:&u32) { self.events.borrow_mut().push(Event::Keep(*k)); }
}
struct Shadow { id:usize, visits:Cell<usize> }
impl Shadow {
    fn span(&self)->(u64,u64) {
        self.visits.set(self.visits.get()+1);
        (self.id as u64*65536,65536)
    }
    fn refresh(&self,l:&List,s:u64,n:u64) {
        l.events.borrow_mut().push(Event::Refresh(self.id,s,n));
    }
    fn gpu_writes(&self,l:&List,s:u64,n:u64) {
        l.events.borrow_mut().push(Event::Write(self.id,s,n));
    }
}
struct Memory { copies:Vec<Shadow>, directory:(u32,), faults:(u32,) }
impl Memory {
    fn new(n:usize)->Self {
        Self {copies:(0..n).map(|id|Shadow{id,visits:Cell::new(0)}).collect(),
            directory:(1,),faults:(2,)}
    }
    fn visits(&self)->usize {self.copies.iter().map(|s|s.visits.get()).sum()}
    fn extend(&mut self,n:usize) {
        let old=self.copies.len();
        self.copies.extend((old..n).map(|id|Shadow{id,visits:Cell::new(0)}));
    }
}
"""
        def function(name, block):
            return "fn "+name+"(m:&Memory,list:&List,numbered:usize,writes:bool) {\n"+block+"}\n"
        cases = """
const R:usize=usize::MAX-0x6d;
const W:usize=usize::MAX-0x6e;
fn check(a:&Memory,b:&Memory,la:&List,lb:&List,numbered:usize,writes:bool) {
    let n=a.copies.len();
    let read=!la.seen.borrow().contains(&R);
    let write=writes&&!la.seen.borrow().contains(&W);
    let mut expected=vec![Event::First(R)];
    if writes { expected.push(Event::First(W)); }
    for i in 0..n {
        let start=i as u64*65536;
        if read||i>=numbered {expected.push(Event::Refresh(i,start,65536));}
        if writes&&(write||i>=numbered) {expected.push(Event::Write(i,start,65536));}
    }
    if read {expected.extend([Event::Keep(1),Event::Keep(2)]);}
    let va=a.visits();
    let vb=b.visits();
    baseline(a,la,numbered,writes);
    candidate(b,lb,numbered,writes);
    assert_eq!(*la.events.borrow(),expected);
    assert_eq!(*lb.events.borrow(),expected);
    assert_eq!(*la.seen.borrow(),*lb.seen.borrow());
    assert_eq!(a.visits()-va,n);
    assert_eq!(b.visits()-vb,if read||write {n} else {n-numbered});
    la.events.borrow_mut().clear();
    lb.events.borrow_mut().clear();
}
#[test]
fn all_prefix_sizes_and_first_use_flags() {
    for n in (0..=128).chain([255,512,1023]) {
        let a=Memory::new(n);
        let b=Memory::new(n);
        for numbered in 0..=n {
            for previous in 0..4 {
                for writes in [false,true] {
                    let la=List::default();
                    let lb=List::default();
                    for l in [&la,&lb] {
                        if previous&1!=0 {l.seen.borrow_mut().insert(R);}
                        if previous&2!=0 {l.seen.borrow_mut().insert(W);}
                    }
                    check(&a,&b,&la,&lb,numbered,writes);
                }
            }
        }
    }
}
#[test]
fn successive_read_write_and_growth_sequences() {
    for schedule in 0..256u32 {
        let mut a=Memory::new(0);
        let mut b=Memory::new(0);
        let la=List::default();
        let lb=List::default();
        for step in 0..8 {
            let old=a.copies.len();
            let new=old+if (schedule>>step)&1!=0 {step+1} else {0};
            a.extend(new);
            b.extend(new);
            check(&a,&b,&la,&lb,old,(schedule>>((step+3)%8))&1!=0);
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/"ready.rs"
            exe = Path(tmp)/"ready"
            src.write_text(prefix+function("baseline",OLD)+function("candidate",NEW)+cases)
            subprocess.run([rustc,"--edition=2021","--test",str(src),"-o",str(exe)],
                           check=True,timeout=90)
            subprocess.run([str(exe)],check=True,timeout=120)


if __name__ == "__main__":
    unittest.main()
