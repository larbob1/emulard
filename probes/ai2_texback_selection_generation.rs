// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to disposable pinned prepared host.rs. No shared submit hooks.
#[cfg(all(test, windows, feature = "diagnostics"))]
mod ai2_selection_generation {
    use super::*;
    use crate::object::This;
    use crate::resource::ai2_record_resource as guest;
    use crate::texback::{self, ai2_generation_observe as obs};
    use windows::core::Interface;
    use windows::Win32::Graphics::Dxgi::{IDXGIAdapter1, DXGI_ADAPTER_FLAG_SOFTWARE};
    use windows_sys::Win32::System::Memory::{VirtualAlloc, VirtualFree, VirtualQuery,
        MEMORY_BASIC_INFORMATION, MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, MEM_PRIVATE, PAGE_READWRITE};

    const ALLOCATION: usize = 65536;
    const PREFIX: usize = 256;
    const SIZE: usize = 2560;

    struct Owned {
        page: *mut u8,
        this: This,
        seed: u8,
    }

    impl Owned {
        fn new(seed: u8) -> Self {
            let page = unsafe { VirtualAlloc(std::ptr::null(),ALLOCATION,
                MEM_RESERVE | MEM_COMMIT,PAGE_READWRITE) }.cast::<u8>();
            assert!(!page.is_null());
            let mut owned = Self { page, this: std::ptr::null(), seed };
            owned.check_page();
            for i in 0..ALLOCATION {
                unsafe { page.add(i).write(owned.expected(i)); }
            }
            owned.this = guest::create(owned.at());
            owned.verify();
            owned
        }
        fn at(&self) -> usize { (unsafe { self.page.add(PREFIX) }) as usize }
        fn expected(&self,i: usize) -> u8 {
            if (PREFIX..PREFIX+SIZE).contains(&i) {
                self.seed.wrapping_add((i as u8).wrapping_mul(37))
            } else { self.seed ^ 0xA5 }
        }
        fn check_page(&self) {
            let mut info: MEMORY_BASIC_INFORMATION = unsafe { std::mem::zeroed() };
            let n = unsafe { VirtualQuery(self.page.cast(),&mut info,std::mem::size_of_val(&info)) };
            assert_eq!(n,std::mem::size_of_val(&info));
            assert_eq!(info.BaseAddress as usize,self.page as usize);
            assert_eq!(info.AllocationBase as usize,self.page as usize);
            assert_eq!(info.State,MEM_COMMIT);
            assert_eq!(info.Protect,PAGE_READWRITE);
            assert_eq!(info.Type,MEM_PRIVATE);
            assert!(info.RegionSize>=ALLOCATION);
            assert_eq!(self.at()%256,0);
        }
        fn verify(&self) {
            self.check_page();
            let bytes = unsafe { std::slice::from_raw_parts(self.page,ALLOCATION) };
            for (i,&b) in bytes.iter().enumerate() {
                assert_eq!(b,self.expected(i),"owned byte {i}");
            }
        }
    }

    impl Drop for Owned {
        fn drop(&mut self) {
            if !self.this.is_null() {
                guest::release(self.this,self.at());
                self.this = std::ptr::null();
                if !std::thread::panicking() { self.verify(); }
            }
            assert_ne!(unsafe { VirtualFree(self.page.cast(),0,MEM_RELEASE) },0);
        }
    }

    fn preflight() -> &'static Host {
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(),Ok("1"));
        assert_eq!(std::env::var("VICTORY_SWEEP").as_deref(),Ok("0"));
        assert_eq!(std::env::var("VICTORY_TEXTURE_BACK").as_deref(),Ok("7x3f61"));
        assert!(std::env::var_os("VICTORY_COPY_MODE").is_none());
        assert!(std::env::var_os("VICTORY_GPU_TIMING").is_none());
        assert_eq!(crate::copystat::mode(),0);
        assert!(!timing());
        let h = host().expect("owned WARP host");
        let warp = warp_adapter().expect("strict WARP adapter");
        let desc = unsafe { warp.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        let actual = unsafe { h.device.GetAdapterLuid() };
        assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32,0);
        assert_eq!((actual.HighPart,actual.LowPart),(desc.AdapterLuid.HighPart,desc.AdapterLuid.LowPart));
        no_submission(h);
        eprintln!("selection_adapter actual_high={} actual_low={} warp_high={} warp_low={} software=1",
            actual.HighPart,actual.LowPart,desc.AdapterLuid.HighPart,desc.AdapterLuid.LowPart);
        h
    }

    fn no_submission(h: &Host) {
        assert_eq!(*h.submitted.lock().unwrap(),0);
        assert_eq!(STARTED.load(Ordering::Acquire),0);
        assert_eq!(FINISHED.load(Ordering::Acquire),0);
        assert_eq!(unsafe { h.fence.GetCompletedValue() },0);
        unsafe { h.device.GetDeviceRemovedReason().unwrap(); }
    }

    // The observer clones at most two actual Arc identities under a short guard.
    // No guard survives either function, including across invalidation or close.
    fn selected(l: &HostList) -> [Option<obs::TargetView>;2] {
        let d = l.deferred();
        assert!(d.back_wanted.len()<=2);
        assert!(d.texture_backs.is_empty());
        std::array::from_fn(|i| d.back_wanted.get(i).map(obs::target))
    }

    fn recorded(l: &HostList) -> [Option<obs::TicketView>;2] {
        let d = l.deferred();
        assert!(d.back_wanted.is_empty());
        assert!(d.texture_backs.len()<=2);
        std::array::from_fn(|i| d.texture_backs.get(i).map(obs::back))
    }

    fn identity(v: &obs::TargetView, o: &Owned) {
        assert_eq!(v.ticket.owner(),o.this as usize);
        assert_eq!(v.ticket.range(),(o.at(),o.at()+SIZE));
        let copy = crate::resource::host_copy(o.this).expect("same live host texture");
        assert!(std::sync::Arc::ptr_eq(&v.copy,&copy));
    }

    fn run(id: u32) {
        assert!(id<=11);
        let h = preflight();
        let a = Owned::new(0x43);
        let b = (id==11).then(|| Owned::new(0xB9));
        let distinct = b.is_some();
        if let Some(b) = &b {
            assert_ne!(a.this,b.this);
            assert!(a.at()+SIZE<=b.at() || b.at()+SIZE<=a.at());
        }
        let l = h.new_list().expect("real HostList");
        assert!(selected(&l).iter().all(Option::is_none));
        assert!(texback::wanted(a.this));
        l.texture_written(a.this);
        let first = selected(&l);
        let original = first[0].as_ref().expect("first real selection");
        assert!(first[1].is_none());
        identity(original,&a);
        assert!(original.ticket.valid());

        // Direct ticket seam only: no actual memory remapping or shader execution.
        // Empty interior ranges intentionally expose the current predicate, not
        // actual empty-map reachability. All ranges lie in owned private pages.
        let range = match id {
            0 | 11 => None,
            1 => Some((a.at()-16,16)),
            2 => Some((a.at()+SIZE,16)),
            3 => Some((a.at(),1)),
            4 => Some((a.at()+SIZE-1,1)),
            5 => Some((a.at()+256,256)),
            6 => Some((a.at(),SIZE)),
            7 => Some((a.at(),0)),
            8 => Some((a.at()+256,0)),
            9 => Some((a.at()+SIZE-1,0)),
            10 => Some((a.at()+SIZE,0)),
            _ => unreachable!(),
        };
        let invalidated = matches!(id,3|4|5|6|8|9);
        if let Some((at,len)) = range { texback::remapped(at,len); }
        assert_eq!(original.ticket.valid(),!invalidated);
        let before_second = selected(&l);
        let held = before_second[0].as_ref().unwrap();
        assert!(held.ticket.same(&original.ticket));
        assert_eq!(held.ticket.valid(),!invalidated);
        assert!(before_second[1].is_none());
        a.verify();

        // Independent legitimate second intent, eligible current resource, and
        // actual independently-created ticket. Its weak registry entry is
        // diagnostic only and never enters the list's deferred selection.
        let current = b.as_ref().unwrap_or(&a);
        let eligible = obs::eligible(current.this,current.at());
        identity(&eligible,current);
        assert!(eligible.ticket.valid());
        assert!(!eligible.ticket.same(&original.ticket));
        assert_eq!(std::sync::Arc::ptr_eq(&eligible.copy,&original.copy),!distinct);
        assert!(texback::wanted(current.this));
        l.texture_written(current.this);
        let after = selected(&l);
        let kept = after[0].as_ref().unwrap();
        assert!(kept.ticket.same(&original.ticket));
        assert_eq!(kept.ticket.valid(),!invalidated);
        identity(kept,&a);
        assert!(eligible.ticket.valid());
        let selected_count = if distinct { 2 } else { 1 };
        assert_eq!(after.iter().flatten().count(),selected_count);
        if distinct {
            let next = after[1].as_ref().unwrap();
            identity(next,current);
            assert!(next.ticket.valid());
            assert!(!next.ticket.same(&original.ticket));
            assert!(!next.ticket.same(&eligible.ticket));
            assert!(std::sync::Arc::ptr_eq(&next.copy,&eligible.copy));
        } else {
            assert!(after[1].is_none());
        }
        let live = after.iter().flatten().filter(|v| v.ticket.valid()).count();
        let expected_live = if invalidated {0} else {selected_count};
        assert_eq!(live,expected_live);

        // Actual close records any surviving current Back. This is a baseline
        // witness of current behavior, never a claim of safe suppression.
        // HostList may settle a state before refusing record. No submission,
        // prelude execution, readback mapping, land, or publication occurs.
        l.close();
        let backs = recorded(&l);
        assert_eq!(backs.iter().flatten().count(),expected_live);
        for (i,ticket) in backs.iter().flatten().enumerate() {
            assert!(ticket.same(&after[i].as_ref().unwrap().ticket));
            assert!(ticket.valid());
            assert!(!ticket.same(&eligible.ticket));
        }
        a.verify();
        if let Some(b) = &b { b.verify(); }
        no_submission(h);

        // Drop the unsubmitted list first, keeping all guest resources live.
        drop(l);
        a.verify();
        if let Some(b) = &b { b.verify(); }
        drop(b);
        drop(a);
        assert!(!original.ticket.valid());
        assert!(!eligible.ticket.valid());
        for view in after.iter().flatten() { assert!(!view.ticket.valid()); }
        for ticket in backs.iter().flatten() { assert!(!ticket.valid()); }
        drop(backs); drop(after); drop(before_second); drop(first); drop(eligible);
        no_submission(h);
        eprintln!("selection_case id={} second_intent=1 independent_eligible=1 invalidated={} distinct={} selected={} live={} recorded={} missing_current={} submitted=0 healthy=1 preserved={} guards={} cleanup=1",
            id,u8::from(invalidated),u8::from(distinct),selected_count,live,expected_live,
            u8::from(invalidated),SIZE*selected_count,(ALLOCATION-SIZE)*selected_count);
    }

    macro_rules! case {
        ($name:ident,$id:expr) => {
            #[test]
            #[ignore = "requires isolated WARP process; baseline selection witness only"]
            fn $name() { run($id); }
        };
    }
    case!(actual_selection_repeat,0);
    case!(actual_selection_left_adjacent,1);
    case!(actual_selection_right_adjacent,2);
    case!(actual_selection_first_byte,3);
    case!(actual_selection_last_byte,4);
    case!(actual_selection_interior,5);
    case!(actual_selection_full,6);
    case!(actual_selection_empty_start,7);
    case!(actual_selection_empty_interior,8);
    case!(actual_selection_empty_last,9);
    case!(actual_selection_empty_end,10);
    case!(actual_selection_distinct_owner,11);
}
