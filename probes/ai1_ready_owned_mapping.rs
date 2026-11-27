
#[cfg(all(test, feature = "diagnostics"))]
mod ai1_ready_owned_review {
    use super::*;
    use std::cell::RefCell;
    use windows::core::Interface;

    use windows_sys::Win32::System::Memory::{
        VirtualAlloc, VirtualFree, MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, PAGE_READWRITE
    };
    // A fixed requested address is not authority to read it. Only a
    // successful allocation returning that exact address grants ownership.
    const A: u64 = 0x1_0001_0000;
    const B: u64 = A + PAGE;
    const C: u64 = B + PAGE;
    const BYTES: usize = 3 * PAGE as usize;
    thread_local! {
        static OWNED: RefCell<HashMap<u64, Arc<Shadow>>> = RefCell::new(HashMap::new());
    }
    struct Allocation(*mut core::ffi::c_void, usize);
    impl Allocation {
        fn new() -> Self {
            let p = unsafe { VirtualAlloc(A as *const _, BYTES, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) };
            assert!(!p.is_null(), "bounded owned allocation unavailable");
            let mut owned = Self(p, 0);
            assert_eq!(p as u64, A, "unexpected allocation address");
            assert!(C / PAGE < u64::from(MEMORY_PAGES) - 1);
            // Only touch bytes returned by the allocation.
            unsafe { std::ptr::write_bytes(p.cast::<u8>(), 0x5a, BYTES) };
            for at in [A,B,C] {
                assert!(crate::shadow::extent(at).is_none());
            }
            for at in [A,B,C] {
                crate::shadow::register(at as usize, at, PAGE);
                owned.1 += 1;
            }
            owned
        }
    }
    impl Drop for Allocation {
        fn drop(&mut self) {
            // No list was submitted. On failure drop Memory and fixture
            // references before freeing owned pages. The registry is local
            // to this exact fresh test process.
            if self.1 != 0 {
                let memory = MEMORY.lock().unwrap_or_else(|e| e.into_inner()).take();
                drop(memory);
                OWNED.with(|m| m.borrow_mut().clear());
                for at in [A,B,C].into_iter().take(self.1) {
                    crate::shadow::unregister(at as usize, at);
                }
            }
            let freed = unsafe { VirtualFree(self.0, 0, MEM_RELEASE) };
            if !std::thread::panicking() { assert_ne!(freed,0); }
        }
    }
    pub(super) fn owns(at: u64, len: u64) -> bool {
        len == PAGE && OWNED.with(|m| m.borrow().contains_key(&at))
    }
    type Event = (u8, u64, usize);
    type Snapshot = (Vec<Event>, usize, bool, bool, usize);
    fn snap(list: &HostList) -> Snapshot {
        let (steps, kept, r, w, refreshed) = list.ai1_prefix_snapshot();
        let events = steps.into_iter().map(|(kind, ptr, at, len)| {
            if kind == 3 { return (3, 0, 0); }
            let address = at as u64;
            OWNED.with(|m| {
                let m = m.borrow();
                let copy = m.get(&address).expect("nonowned step");
                assert_eq!(ptr, Arc::as_ptr(copy) as usize);
                assert_eq!(len, PAGE as usize);
            });
            (kind, address, len)
        }).collect();
        (events, kept.len(), r, w, refreshed)
    }
    fn state(f: impl FnOnce(&mut Memory)) {
        let mut guard = MEMORY.lock().unwrap_or_else(|e| e.into_inner());
        f(guard.as_mut().expect("actual Memory::new"));
    }
    fn check_directory(m: &Memory, expected: &[u64]) {
        assert_eq!(m.copies.len(), expected.len());
        for (i, at) in expected.iter().copied().enumerate() {
            assert_eq!(m.copies[i].span(), (at, PAGE));
            OWNED.with(|owned| assert!(Arc::ptr_eq(&m.copies[i], &owned.borrow()[&at])));
            let page = at / PAGE;
            assert!(page < u64::from(MEMORY_PAGES) - 1);
            let entry = unsafe { m.directory.1.add(page as usize * 2) };
            assert_eq!(unsafe { entry.read() }, i as u32 + 1);
            assert_eq!(unsafe { entry.add(1).read() }, 0);
        }
        for at in [A, B, C] {
            if !expected.contains(&at) {
                assert_eq!(unsafe { m.directory.1.add((at/PAGE) as usize * 2).read() }, 0);
            }
        }
        let last = (MEMORY_PAGES as usize - 1) * 2;
        assert_eq!(unsafe { m.directory.1.add(last).read() }, 0);
    }
    fn event(kind: u8, at: u64) -> Event { (kind, at, PAGE as usize) }
    fn run(call: fn(&HostList, &HostHeap, &[u64], &[u32], bool) -> Option<Ready>)
        -> Vec<Snapshot>
    {
        assert!(MEMORY.lock().unwrap_or_else(|e| e.into_inner()).is_none());
        let allocation = Allocation::new();
        OWNED.with(|m| {
            let mut m = m.borrow_mut();
            assert!(m.is_empty());
            for at in [A,B,C] {
                assert!(at / PAGE < u64::from(MEMORY_PAGES) - 1);
                assert_eq!(crate::shadow::extent(at),Some((at,PAGE)));
                assert!(crate::texture::committed(at as *const u8, PAGE as usize));
                m.insert(at, crate::shadow::find(at, PAGE).expect("actual registered shadow"));
            }
        });
        let h = host().expect("WARP host required");
        let bad = HostHeap::new(true, 1).expect("sampler heap");
        let heap1 = HostHeap::new(false, 1).expect("view heap 1");
        let heap2 = HostHeap::new(false, 1).expect("view heap 2");
        let a = h.new_list().expect("list A");
        let b = h.new_list().expect("list B");
        let mut traces = Vec::new();
        let mut expected = vec![];
        // Actual heap allocation refusal happens AFTER named copy publication.
        assert!(call(&a,&bad,&[A],&[],false).is_none());
        assert_eq!(snap(&a), (vec![],0,false,false,0));
        state(|m| {
            check_directory(m,&[A]);
            assert!(m.heaps.is_empty());
            assert!(m.refused.contains(&(((A & !(CELL - 1)) + CELL)/PAGE)));
        });
        let ready = call(&a,&heap1,&[],&[],false).expect("first ready");
        let base = ready.base;
        state(|m| {
            assert_eq!(ready.directory,m.directory.2);
            assert_eq!(ready.faults,m.faults.2);
            assert_eq!(m.heaps[&(std::ptr::from_ref(&heap1) as usize)],(base,1));
        });
        expected.push(event(1,A));
        assert_eq!(snap(&a),(expected.clone(),2,true,false,1));
        traces.push(snap(&a));
        assert_eq!(call(&a,&heap1,&[A],&[],false).unwrap().base,base);
        assert_eq!(snap(&a),(expected.clone(),2,true,false,1));
        traces.push(snap(&a));
        assert!(call(&a,&heap1,&[],&[],true).is_some());
        expected.push(event(2,A));
        assert_eq!(snap(&a),(expected.clone(),2,true,true,1));
        traces.push(snap(&a));
        // Force only the local memory frame cache to differ. Do not modify
        // the actual frame clock. The actual take_faults path runs next.
        state(|m| {
            m.frame = crate::frame::current().wrapping_add(1);
            assert!(MEMORY_FAULTS > 1);
            unsafe {
                m.faults.1.write(0x1234);
                m.faults.1.add(1).write((B/PAGE) as u32);
            }
        });
        assert!(call(&a,&heap1,&[],&[],true).is_some());
        state(|m| {
            check_directory(m,&[A,B]);
            assert_eq!(unsafe { m.faults.1.read() },0x1234);
            assert_eq!(unsafe { m.faults.1.add(1).read() },0);
            assert!(m.refused.is_empty());
            assert_eq!(m.heaps[&(std::ptr::from_ref(&heap1) as usize)],(base,2));
        });
        // Existing limitation: fault append precedes numbered snapshot.
        assert_eq!(snap(&a),(expected.clone(),2,true,true,1));
        traces.push(snap(&a));
        assert!(call(&a,&heap1,&[],&[C as u32,(C>>32) as u32],true).is_some());
        expected.extend([event(1,C),event(2,C)]);
        assert_eq!(snap(&a),(expected.clone(),2,true,true,2));
        traces.push(snap(&a));
        let rb = call(&b,&heap2,&[],&[],false).expect("second heap ready");
        let all = vec![event(1,A),event(1,B),event(1,C)];
        assert_eq!(snap(&b),(all,2,true,false,3));
        traces.push(snap(&b));
        state(|m| {
            check_directory(m,&[A,B,C]);
            assert_eq!(m.heaps.len(),2);
            assert_eq!(m.heaps[&(std::ptr::from_ref(&heap1) as usize)],(base,3));
            assert_eq!(m.heaps[&(std::ptr::from_ref(&heap2) as usize)],(rb.base,3));
        });
        a.defer(|| {});
        expected.push((3,0,0));
        assert!(call(&a,&heap1,&[],&[],true).is_some());
        assert_eq!(snap(&a),(expected,2,true,true,0));
        traces.push(snap(&a));
        unsafe { a.list.Close().expect("close A"); }
        a.reset();
        assert_eq!(snap(&a),(vec![],0,false,false,0));
        assert!(call(&a,&heap1,&[],&[],true).is_some());
        let fresh = [A,B,C].into_iter().flat_map(|at| [event(1,at),event(2,at)]).collect();
        assert_eq!(snap(&a),(fresh,2,true,true,3));
        traces.push(snap(&a));
        unsafe { a.list.Close().expect("close A"); b.list.Close().expect("close B"); }
        drop(a);
        drop(b);
        // Drop global Memory while the heaps are still live; no stale heap
        // keys survive the variant. The fixture still owns every copy.
        let memory = MEMORY.lock().unwrap_or_else(|e| e.into_inner()).take();
        drop(memory);
        drop(heap1);
        drop(heap2);
        drop(bad);
        OWNED.with(|m| {
            let mut m = m.borrow_mut();
            for copy in m.values() { assert_eq!(Arc::strong_count(copy),2); }
            m.clear();
        });
        drop(allocation);
        for at in [A,B,C] { assert!(crate::shadow::extent(at).is_none()); }
        traces
    }
    #[test]
    fn actual_ready_owned_mapping_parity() {
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(),Ok("1"));
        assert!(host().expect("host").ai1_prefix_software());
        assert_eq!(crate::inplace::level(),0);
        assert!(!crate::shadow::cards());
        let original = run(ready);
        let candidate = run(ready_skip_prefix);
        assert_eq!(original,candidate);
        assert_eq!(original.len(),8);
    }
}
