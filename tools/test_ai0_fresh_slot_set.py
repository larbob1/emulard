# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile exact descriptor classification prefixes against synthetic heap seams."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from preview_ai0_fresh_slot_set import START, END, OLD, NEW, blob, clone, preview


class FreshSlotSetReview(unittest.TestCase):
    def source(self):
        return (START + ") {\n" + OLD + "            // original tail\n        }\n" + END + "\n").encode()

    def test_append_only(self):
        data = self.source()
        result = preview(data, blob(data))
        self.assertTrue(result.startswith(data))
        candidate = clone(data.decode())
        self.assertIn(NEW, candidate)
        self.assertNotIn(OLD, candidate)
        self.assertIn("// original tail", candidate)

    def test_refuse_drift(self):
        data = self.source()
        with self.assertRaises(ValueError):
            preview(data)
        for changed in (data+data, data.replace(OLD.encode(), b"// drift"), data+b"tables_fresh_mask"):
            with self.assertRaises(ValueError):
                preview(changed, blob(changed))

    def test_exact_prefix_parity(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required")
        prefix = """
#[derive(Clone,Copy,PartialEq,Eq)]
enum RootType { Table, Other }
#[derive(Clone,Copy,PartialEq,Eq)]
enum ResourceType { Cbv, Srv }
#[derive(Clone,Copy)]
struct UsedResource { root: RootType, kind: ResourceType, slot: u8, table_offset_dwords: u32 }
#[derive(Clone,Copy)]
enum Root { None, Table(u64) }
struct Host { count: u32 }
impl Host { fn count(&self)->u32 { self.count } }
struct Heap { host: Option<Host> }
impl Heap {
    fn host(&self)->Option<&Host> { self.host.as_ref() }
    fn index(&self, addr:u64)->Option<u32> {
        if (100..164).contains(&addr) { Some((addr-100) as u32/4) } else { None }
    }
}
struct HostList;
struct State { roots: Vec<Root>, heap: Heap, events: Vec<(u8,u32)> }
impl State {
    fn roots_ref(&self,_:bool)->&Vec<Root> { &self.roots }
    fn heap_of(&self,table:u64)->Option<&Heap> {
        if (100..164).contains(&table) { Some(&self.heap) } else { None }
    }
    fn table_entry(&mut self,_:&HostList,u:&UsedResource,_:bool) {
        self.events.push((u.slot,u.table_offset_dwords));
    }
"""
        def function(name, block):
            return ("fn "+name+"(&mut self, list:&HostList, used:&[UsedResource], compute:bool) -> Vec<(u8,u32)> {\n"
                    +block+"made.push((slot,0));\n}\nmade\n}\n")
        rust_tests = """
}
fn resource(slot:u8, kind:ResourceType, root:RootType, offset:u32)->UsedResource {
    UsedResource { slot, kind, root, table_offset_dwords:offset }
}
fn state(mode:u32)->State {
    let roots = (0..256).map(|slot| match (slot+mode)%4 {
        0 => Root::None, 1 => Root::Table(100), 2 => Root::Table(140), _ => Root::Table(1000)
    }).collect();
    State { roots, heap: Heap { host: if mode%5==0 {None} else {Some(Host{count:mode%16})} },
        events:Vec::new() }
}
fn check(used:&[UsedResource], mode:u32) {
    let mut a=state(mode);
    let mut b=state(mode);
    let mut expected=std::collections::BTreeSet::new();
    for u in used {
        if u.root!=RootType::Table { continue; }
        if u.kind==ResourceType::Cbv { expected.insert(u.slot); continue; }
        if let Some(Root::Table(table))=a.roots.get(usize::from(u.slot)) {
            if let Some(heap)=a.heap_of(*table) {
                if let (Some(host),Some(index))=(heap.host(),heap.index(*table+u64::from(u.table_offset_dwords)*4)) {
                    if index>=host.count() { expected.insert(u.slot); }
                }
            }
        }
    }
    let events:Vec<_>=used.iter().filter(|u|u.root==RootType::Table&&!expected.contains(&u.slot))
        .map(|u|(u.slot,u.table_offset_dwords)).collect();
    let fresh:Vec<_>=expected.into_iter().map(|slot|(slot,0)).collect();
    assert_eq!(a.baseline(&HostList,used,false),fresh);
    assert_eq!(b.candidate(&HostList,used,false),fresh);
    assert_eq!(a.events,events);
    assert_eq!(b.events,events);
}
#[test]
fn every_slot_and_duplicate_order() {
    for mode in 0..20 {
        check(&[],mode);
        let mut used=Vec::new();
        for slot in 0..=255u8 {
            let one=resource(slot,ResourceType::Cbv,RootType::Table,0);
            let two=resource(slot,ResourceType::Srv,RootType::Table,u32::from(slot)%25);
            let three=resource(slot,ResourceType::Cbv,RootType::Other,1);
            check(&[two,one,one,three],mode);
            used.extend([two,three]);
            if u32::from(slot)%7==mode%7 { used.extend([one,one]); }
        }
        check(&used,mode);
        used.reverse();
        check(&used,mode);
    }
}
#[test]
fn dense_and_boundary_sets() {
    for mode in 0..20 {
        let used:Vec<_>=(0..=255u8).rev().map(|s|resource(s,ResourceType::Cbv,RootType::Table,0)).collect();
        check(&used,mode);
        for slots in [[0,63,64,127,128,191,192,255],[1,62,65,126,129,190,193,254]] {
            let entries:Vec<_>=slots.into_iter().map(|s|resource(s,ResourceType::Cbv,RootType::Table,0)).collect();
            check(&entries,mode);
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/"fresh.rs"
            exe = Path(tmp)/"fresh"
            src.write_text(prefix+function("baseline",OLD)+function("candidate",NEW)+rust_tests)
            subprocess.run([rustc,"--edition=2021","--test",str(src),"-o",str(exe)],check=True,timeout=90)
            subprocess.run([str(exe)],check=True,timeout=30)


if __name__ == "__main__":
    unittest.main()
