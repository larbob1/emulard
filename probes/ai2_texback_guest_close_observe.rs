// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to disposable prepared texback.rs. Test-only one-shot observation.
#[cfg(all(test, windows, feature = "diagnostics"))]
pub(crate) mod ai2_guest_close_observe {
    use super::*;
    use std::cell::RefCell;

    #[derive(Clone)]
    pub(crate) struct Selected {
        ticket: Arc<Ticket>,
        pub(crate) copy: Arc<crate::resource::HostTexture>,
    }
    impl Selected {
        pub(crate) fn owner(&self) -> usize { self.ticket.owner }
        pub(crate) fn range(&self) -> (usize, usize) { (self.ticket.at,self.ticket.end) }
        pub(crate) fn valid(&self) -> bool { self.ticket.valid.load(Ordering::Acquire) }
    }
    pub(crate) fn selected(t: &Target) -> Selected {
        assert_eq!((t.layout.size,t.layout.slice_size,t.layout.slices),(2560,1280,2));
        assert_eq!((t.layout.mips[0].offset,t.layout.mips[1].offset),(512,0));
        assert_eq!((t.layout.mips[0].pitch,t.layout.mips[1].pitch),(256,256));
        Selected { ticket: t.ticket.clone(), copy: t.copy.clone() }
    }

    pub(crate) type Shape = (u64,i32,u32,u32,u32,u32,u32);
    pub(crate) fn shape(f: &D3D12_PLACED_SUBRESOURCE_FOOTPRINT, rows: u32) -> Shape {
        let p = f.Footprint;
        (f.Offset,p.Format.0,p.Width,p.Height,p.Depth,p.RowPitch,rows)
    }
    #[derive(Debug,PartialEq,Eq)]
    pub(crate) struct Seen {
        pub(crate) valid: bool,
        pub(crate) extent: u64,
        pub(crate) count: usize,
        pub(crate) shapes: [Shape;4],
    }
    struct Armed {
        ticket: Arc<Ticket>,
        refuse: bool,
        hits: u32,
        seen: Option<Seen>,
    }
    thread_local! {
        static ARM: RefCell<Option<Armed>> = const { RefCell::new(None) };
    }
    pub(crate) fn arm(s: &Selected, refuse: bool) {
        assert!(s.valid());
        ARM.with(|slot| {
            let mut slot = slot.borrow_mut();
            assert!(slot.is_none());
            *slot = Some(Armed { ticket:s.ticket.clone(),refuse,hits:0,seen:None });
        });
    }

    // Runs inside the guest ABI close path: no assertions, heap allocation,
    // logging or unwinding. No matching ticket means no intervention.
    pub(super) fn before_allocation(t: &Target, total: u64,
        f: &[D3D12_PLACED_SUBRESOURCE_FOOTPRINT], rows: &[u32]) -> bool {
        ARM.try_with(|cell| {
            let Ok(mut slot) = cell.try_borrow_mut() else { return false };
            let Some(a) = slot.as_mut() else { return false };
            if !Arc::ptr_eq(&a.ticket,&t.ticket) { return false; }
            a.hits = a.hits.saturating_add(1);
            if a.hits != 1 { return false; }
            let mut shapes = [(0,0,0,0,0,0,0);4];
            for ((out,fp),&n) in shapes.iter_mut().zip(f).zip(rows) {
                *out = shape(fp,n);
            }
            a.seen = Some(Seen { valid:t.ticket.valid.load(Ordering::Acquire),
                extent:total,count:f.len().min(rows.len()),shapes });
            a.refuse
        }).unwrap_or(false)
    }
    pub(crate) fn finish() -> Seen {
        ARM.with(|slot| {
            let a = slot.borrow_mut().take().expect("armed selected target");
            assert_eq!(a.hits,1);
            a.seen.expect("observed allocation boundary")
        })
    }
    pub(crate) fn recorded(b: &Back, s: &Selected) -> (u64,[Shape;4]) {
        assert!(Arc::ptr_eq(&b.ticket,&s.ticket));
        assert!(s.valid());
        assert_eq!((b.footprints.len(),b.rows.len(),b.mips),(4,4,2));
        (unsafe { b.buffer.GetDesc().Width },
            std::array::from_fn(|i| shape(&b.footprints[i],b.rows[i])))
    }
}
