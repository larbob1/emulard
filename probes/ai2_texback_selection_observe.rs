// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to a disposable pinned prepared texback.rs.
#[cfg(all(test, windows, feature = "diagnostics"))]
pub(crate) mod ai2_generation_observe {
    use super::*;

    // Retain the actual generation, not a numeric pointer identity.
    #[derive(Clone)]
    pub(crate) struct TicketView(Arc<Ticket>);

    impl TicketView {
        pub(crate) fn owner(&self) -> usize { self.0.owner }
        pub(crate) fn range(&self) -> (usize,usize) { (self.0.at,self.0.end) }
        pub(crate) fn valid(&self) -> bool { self.0.valid.load(Ordering::Acquire) }
        pub(crate) fn same(&self, other: &Self) -> bool { Arc::ptr_eq(&self.0,&other.0) }
    }

    #[derive(Clone)]
    pub(crate) struct TargetView {
        pub(crate) ticket: TicketView,
        pub(crate) copy: Arc<crate::resource::HostTexture>,
    }

    pub(crate) fn target(t: &Target) -> TargetView {
        TargetView{ticket:TicketView(t.ticket.clone()),copy:t.copy.clone()}
    }

    pub(crate) fn back(b: &Back) -> TicketView {
        TicketView(b.ticket.clone())
    }

    // A separate eligibility observation creates a real ticket and therefore
    // adds a weak registry entry. It is never inserted into the HostList.
    pub(crate) fn eligible(this: This, at: usize) -> TargetView {
        assert!(wanted(this));
        let t = Target::new(this).expect("independent selected current target");
        assert_eq!(t.owner(),this as usize);
        assert_eq!((t.ticket.at,t.ticket.end),(at,at+2560));
        assert!(t.ticket.valid.load(Ordering::Acquire));
        assert_eq!((t.layout.size,t.layout.slice_size,t.layout.slices),(2560,1280,2));
        assert_eq!((t.layout.mips[0].offset,t.layout.mips[1].offset),(512,0));
        assert_eq!((t.layout.mips[0].rows,t.layout.mips[1].rows),(3,2));
        assert_eq!((t.layout.mips[0].pitch,t.layout.mips[1].pitch),(256,256));
        assert!(t.copy.tiled.is_none());
        target(&t)
    }
}
