# SPDX-License-Identifier: GPL-3.0-or-later
"""Identity parity using real Arc allocations, not actual GPU mapping."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from preview_ai0_copy_identity_index import (
    STRUCT, STRUCT_END, IMPL, IMPL_END, FIELD, INIT, OLD, NEW, blob, clone, preview,
)


class CopyIdentityIndexReview(unittest.TestCase):
    def source(self):
        return (STRUCT + "\n" + FIELD + STRUCT_END + "\n// mock\n" + IMPL
                + "\n    fn new() -> Option<Memory> {\n        Some(Memory {\n"
                + INIT + "        })\n    }\n    fn map() {\n" + OLD
                + "                // unchanged publication\n"
                + "            }\n        };\n    }" + IMPL_END + "\n").encode()

    def test_append_only_exact_anchors(self):
        data = self.source()
        generated = preview(data, blob(data))
        self.assertTrue(generated.startswith(data))
        candidate = clone(data.decode())
        self.assertIn("copy_index: HashMap<usize, usize>", candidate)
        self.assertIn("Some(MemoryIndexed {", candidate)
        self.assertIn(NEW, candidate)
        self.assertNotIn(OLD, candidate)
        self.assertIn("// unchanged publication", candidate)

    def test_refuse_drift(self):
        data = self.source()
        with self.assertRaises(ValueError):
            preview(data)
        for changed in (data+data, data.replace(OLD.encode(), b"// drift"),
                        data+b"MemoryIndexed", data.replace(INIT.encode(), b"")):
            with self.assertRaises(ValueError):
                preview(changed, blob(changed))

    def test_exact_lookup_prefix_with_real_arc_identity(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required")
        prefix = """
use std::sync::{Arc,Weak};
use std::collections::HashMap;
const COPIES:u32=1023;
struct Shadow { payload:u64 }
#[derive(Default)]
struct Memory { copies:Vec<Arc<Shadow>>, copy_index:HashMap<usize,usize> }
impl Memory {
"""
        def function(name, block):
            return ("fn "+name+"(&mut self,shadow:Arc<Shadow>)->Option<usize> {\n"
                    +block+"                n\n            }\n            None=>return None,\n"
                    "        };\n        Some(n)\n    }\n")
        cases = """
}
fn check(a:&mut Memory,b:&mut Memory,s:&Arc<Shadow>,expected:Option<usize>) {
    assert_eq!(a.baseline(s.clone()),expected);
    assert_eq!(b.candidate(s.clone()),expected);
    assert_eq!(a.copies.len(),b.copies.len());
    assert_eq!(b.copy_index.len(),b.copies.len());
    for (n,(x,y)) in a.copies.iter().zip(&b.copies).enumerate() {
        assert!(Arc::ptr_eq(x,y));
        assert_eq!(b.copy_index.get(&(Arc::as_ptr(y) as usize)),Some(&n));
    }
}
#[test]
fn capacity_duplicate_and_equal_payload_distinct_identity() {
    let mut a=Memory::default();
    let mut b=Memory::default();
    let all:Vec<_>=(0..COPIES+16).map(|_|Arc::new(Shadow{payload:7})).collect();
    for (i,s) in all.iter().enumerate() {
        assert_eq!(s.payload,7);
        check(&mut a,&mut b,s,if i<COPIES as usize {Some(i)} else {None});
    }
    for i in (0..all.len()).rev() {
        check(&mut a,&mut b,&all[i],if i<COPIES as usize {Some(i)} else {None});
    }
    for i in 0..COPIES as usize {
        let n=(i*37)%COPIES as usize;
        check(&mut a,&mut b,&all[n],Some(n));
    }
}
#[test]
fn retained_identity_and_no_extra_strong_owner() {
    let mut a=Memory::default();
    let mut b=Memory::default();
    let s=Arc::new(Shadow{payload:42});
    let w:Weak<Shadow>=Arc::downgrade(&s);
    check(&mut a,&mut b,&s,Some(0));
    assert_eq!(Arc::strong_count(&s),3);
    drop(s);
    let s=w.upgrade().unwrap();
    assert_eq!(s.payload,42);
    assert_eq!(Arc::strong_count(&s),3);
    check(&mut a,&mut b,&s,Some(0));
    drop(a);
    assert_eq!(Arc::strong_count(&s),2);
    drop(b);
    assert_eq!(Arc::strong_count(&s),1);
    drop(s);
    assert!(w.upgrade().is_none());
}
#[test]
fn mixed_repeated_requests_keep_first_seen_number() {
    let all:Vec<_>=(0..256).map(|i|Arc::new(Shadow{payload:i%4})).collect();
    for seed in 0..16usize {
        let mut a=Memory::default();
        let mut b=Memory::default();
        let mut oracle=vec![None;all.len()];
        let mut next=0;
        for step in 0..512usize {
            let id=(step.wrapping_mul(seed*2+1)+seed*31)%all.len();
            let n=*oracle[id].get_or_insert_with(|| {let n=next;next+=1;n});
            check(&mut a,&mut b,&all[id],Some(n));
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/"identity.rs"
            exe = Path(tmp)/"identity"
            src.write_text(prefix+function("baseline",OLD)+function("candidate",NEW)+cases)
            subprocess.run([rustc,"--edition=2021","--test",str(src),"-o",str(exe)],check=True,timeout=90)
            subprocess.run([str(exe)],check=True,timeout=120)


if __name__ == "__main__":
    unittest.main()
