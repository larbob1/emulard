
#[cfg(all(test, feature = "diagnostics"))]
mod ai1_deferred_refresh_review {
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
    type ReadyFn = fn(&HostList, &HostHeap, &[u64], &[u32], bool) -> Option<Ready>;
    type Bytes = (Vec<u8>, Vec<u8>, Vec<u8>);
    fn bytes() -> Bytes {
        OWNED.with(|m| {
            let m = m.borrow();
            (m[&A].ai1_read_owned(A,PAGE), m[&B].ai1_read_owned(B,PAGE),
             m[&C].ai1_read_owned(C,PAGE))
        })
    }
    fn expected(a: u8, b: u8, c: u8) -> Bytes {
        (vec![a; PAGE as usize], vec![b; PAGE as usize], vec![c; PAGE as usize])
    }
    fn prepare(lists: &[&HostList]) {
        OWNED.with(|m| {
            let m = m.borrow();
            let owned: Vec<_> = [A,B,C].into_iter().map(|at| (at, m[&at].clone())).collect();
            HostList::ai1_run_owned_refreshes(lists, &owned, PAGE);
        });
    }
    fn run(call: ReadyFn, order: u8) -> Vec<Bytes> {
        assert!(MEMORY.lock().unwrap_or_else(|e| e.into_inner()).is_none());
        let allocation = Allocation::new();
        OWNED.with(|m| {
            let mut m = m.borrow_mut();
            assert!(m.is_empty());
            for (at, value) in [(A,0x11),(B,0x22),(C,0x33)] {
                assert!(crate::texture::committed(at as *const u8, PAGE as usize));
                // All writes are inside the verified live allocation.
                unsafe { std::ptr::write_bytes(at as *mut u8, value, PAGE as usize); }
                assert_eq!(crate::shadow::extent(at),Some((at,PAGE)));
                let copy = crate::shadow::find(at,PAGE).expect("registered shadow");
                copy.ai1_seed_owned(at,PAGE,0xe7);
                m.insert(at,copy);
            }
        });
        let h = host().expect("WARP host");
        let heap1 = HostHeap::new(false,1).expect("view heap A");
        let heap2 = HostHeap::new(false,1).expect("view heap B");
        let a = h.new_list().expect("list A");
        let b = h.new_list().expect("list B");
        assert!(call(&a,&heap1,&[A],&[],false).is_some());
        assert!(call(&b,&heap2,&[B],&[],false).is_some());
        assert!(call(&a,&heap1,&[B],&[],false).is_some());
        state(|m| check_directory(m,&[A,B]));
        // Shared existing behavior: A's second call does not add a refresh
        // for B, although B is now in the memory directory.
        assert_eq!(snap(&a),(vec![event(1,A)],2,true,false,1));
        assert_eq!(snap(&b),(vec![event(1,A),event(1,B)],2,true,false,2));
        let mut traces = vec![bytes()];
        assert_eq!(traces[0],expected(0xe7,0xe7,0xe7));
        let mut check = |lists: &[&HostList], want: Bytes| {
            prepare(lists);
            let got = bytes();
            assert_eq!(got,want);
            traces.push(got);
        };
        match order {
            0 => check(&[&a],expected(0x11,0xe7,0xe7)),
            1 => check(&[&a,&b],expected(0x11,0x22,0xe7)),
            2 => check(&[&b,&a],expected(0x11,0x22,0xe7)),
            3 => {
                check(&[&a],expected(0x11,0xe7,0xe7));
                check(&[&b],expected(0x11,0x22,0xe7));
            }
            4 => {
                check(&[&b],expected(0x11,0x22,0xe7));
                check(&[&a],expected(0x11,0x22,0xe7));
            }
            _ => panic!("unexpected order"),
        }
        // Actual read-only preparation did not modify owned CPU bytes.
        for (at,value) in [(A,0x11),(B,0x22),(C,0x33)] {
            let cpu = unsafe { std::slice::from_raw_parts(at as *const u8,PAGE as usize) };
            assert!(cpu.iter().all(|&b| b == value));
        }
        unsafe { a.list.Close().expect("close A"); b.list.Close().expect("close B"); }
        drop(a);
        drop(b);
        let memory = MEMORY.lock().unwrap_or_else(|e| e.into_inner()).take();
        drop(memory);
        drop(heap1);
        drop(heap2);
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
    fn actual_deferred_refresh_parity() {
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(),Ok("1"));
        assert!(host().expect("host").ai1_prefix_software());
        assert_eq!(crate::inplace::level(),0);
        assert!(!crate::shadow::cards());
        for order in 0..5 {
            let original = run(ready,order);
            let candidate = run(ready_skip_prefix,order);
            assert_eq!(original,candidate);
            assert_eq!(original.len(),if order >= 3 {3} else {2});
        }
    }
}
