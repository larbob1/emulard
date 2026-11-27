// SPDX-License-Identifier: GPL-3.0-or-later
//! Review-only logical accounting model. Not linked into the runtime.
//! Callers must prove each event corresponds to an actual lifecycle transition.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct Balance {
    count: u64,
    bytes: u64,
}
impl Balance {
    fn change(self, add: bool, count: u64, bytes: u64) -> Option<Self> {
        let op = if add { u64::checked_add } else { u64::checked_sub };
        Some(Self { count: op(self.count, count)?, bytes: op(self.bytes, bytes)? })
    }
}
#[derive(Clone, Copy, Debug)]
enum Kind { SectionHandle, PageId, TitleView, UniqueShownPage, StorageView }
#[derive(Clone, Copy, Debug)]
enum Event {
    Added(Kind, u64, u64),
    Removed(Kind, u64, u64),
    HostFailure,
    UntrackedMapping,
}
#[derive(Clone, Debug, Default, PartialEq, Eq)]
struct Ledger {
    sections: Balance,
    page_ids: Balance,
    title_views: Balance,
    unique_shown: Balance,
    storage_views: Balance,
    failures: u64,
    untracked: u64,
    invalid: bool,
}
impl Ledger {
    fn balance(&mut self, kind: Kind) -> &mut Balance {
        match kind {
            Kind::SectionHandle => &mut self.sections,
            Kind::PageId => &mut self.page_ids,
            Kind::TitleView => &mut self.title_views,
            Kind::UniqueShownPage => &mut self.unique_shown,
            Kind::StorageView => &mut self.storage_views,
        }
    }
    // A batch is one modeled table transition, not a claim of atomicity in
    // the real runtime. Failed arithmetic cannot leave a partial batch.
    fn apply(&mut self, events: &[Event]) -> bool {
        if self.invalid { return false; }
        let mut next = self.clone();
        for &event in events {
            let ok = match event {
                Event::Added(kind, count, bytes) | Event::Removed(kind, count, bytes) => {
                    let add = matches!(event, Event::Added(..));
                    let b = next.balance(kind);
                    if let Some(updated) = b.change(add, count, bytes) {
                        *b = updated;
                        true
                    } else { false }
                }
                Event::HostFailure => match next.failures.checked_add(1) {
                    Some(n) => { next.failures = n; true },
                    None => false,
                },
                Event::UntrackedMapping => match next.untracked.checked_add(1) {
                    Some(n) => { next.untracked = n; next.invalid = true; true },
                    None => false,
                },
            };
            if !ok { self.invalid = true; return false; }
        }
        // Title view bytes include aliases; unique shown bytes count only
        // first/last entries in the actual shown index, never section size.
        if next.unique_shown.bytes > next.title_views.bytes {
            self.invalid = true;
            return false;
        }
        *self = next;
        !self.invalid
    }
    fn alias_excess_bytes(&self) -> Option<u64> {
        if self.invalid { return None; }
        self.title_views.bytes.checked_sub(self.unique_shown.bytes)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use Event::*;
    use Kind::*;
    const PAGE: u64 = 65536;
    fn add(k: Kind, n: u64, b: u64) -> Event { Added(k,n,b) }
    fn rem(k: Kind, n: u64, b: u64) -> Event { Removed(k,n,b) }
    #[test]
    fn distinct_sections_pages_and_aliases() {
        let mut l = Ledger::default();
        assert!(l.apply(&[add(SectionHandle,1,4*PAGE),add(PageId,4,4*PAGE)]));
        assert!(l.apply(&[add(TitleView,1,2*PAGE),add(UniqueShownPage,2,2*PAGE)]));
        assert!(l.apply(&[add(TitleView,1,2*PAGE)]));
        assert_eq!(l.alias_excess_bytes(),Some(2*PAGE));
        assert_eq!(l.sections.bytes,4*PAGE);
        assert_eq!(l.unique_shown.bytes,2*PAGE);
        assert!(l.apply(&[rem(TitleView,1,2*PAGE)]));
        assert_eq!(l.alias_excess_bytes(),Some(0));
    }
    #[test]
    fn page_free_does_not_unmap_or_close_section() {
        let mut l = Ledger::default();
        assert!(l.apply(&[add(SectionHandle,1,PAGE),add(PageId,1,PAGE),
            add(TitleView,1,PAGE),add(UniqueShownPage,1,PAGE)]));
        assert!(l.apply(&[rem(PageId,1,PAGE)]));
        assert_eq!(l.page_ids.bytes,0);
        assert_eq!(l.sections.bytes,PAGE);
        assert_eq!(l.title_views.bytes,PAGE);
        assert!(l.apply(&[rem(TitleView,1,PAGE),rem(UniqueShownPage,1,PAGE)]));
        assert!(l.apply(&[rem(SectionHandle,1,PAGE)]));
        assert_eq!(l,Ledger::default());
    }
    #[test]
    fn failed_unmap_keeps_existing_logical_view() {
        let mut l = Ledger::default();
        assert!(l.apply(&[add(TitleView,1,PAGE),add(UniqueShownPage,1,PAGE)]));
        let old = l.title_views;
        assert!(l.apply(&[HostFailure]));
        assert_eq!(l.title_views,old);
        assert_eq!(l.failures,1);
    }
    #[test]
    fn partial_neighbor_restore_counts_only_success() {
        let mut l = Ledger::default();
        assert!(l.apply(&[add(TitleView,1,3*PAGE),add(UniqueShownPage,3,3*PAGE)]));
        assert!(l.apply(&[rem(TitleView,1,3*PAGE),rem(UniqueShownPage,3,3*PAGE)]));
        assert!(l.apply(&[add(TitleView,1,PAGE),add(UniqueShownPage,1,PAGE)]));
        assert!(l.apply(&[HostFailure]));
        assert_eq!(l.title_views,Balance{count:1,bytes:PAGE});
        assert_eq!(l.unique_shown.bytes,PAGE);
    }
    #[test]
    fn temporary_views_are_independent_and_failed_cleanup_is_unknown() {
        let mut l = Ledger::default();
        assert!(l.apply(&[add(StorageView,1,2*PAGE)]));
        assert_eq!(l.title_views.bytes,0);
        assert!(l.apply(&[rem(StorageView,1,2*PAGE)]));
        assert_eq!(l.storage_views,Balance::default());
        assert!(l.apply(&[add(StorageView,1,PAGE)]));
        assert!(!l.apply(&[HostFailure,UntrackedMapping]));
        assert_eq!(l.untracked,1);
        assert_eq!(l.storage_views.bytes,PAGE);
        assert_eq!(l.alias_excess_bytes(),None);
    }
    #[test]
    fn missing_transition_invalidates_entire_batch() {
        let mut l = Ledger::default();
        assert!(!l.apply(&[add(SectionHandle,1,PAGE),rem(PageId,1,PAGE)]));
        assert!(l.invalid);
        assert_eq!(l.sections,Balance::default());
        assert!(!l.apply(&[add(PageId,1,PAGE)]));
    }
    #[test]
    fn overflow_does_not_wrap_or_publish_partial_counts() {
        let mut l = Ledger::default();
        assert!(l.apply(&[add(SectionHandle,1,u64::MAX)]));
        assert!(!l.apply(&[add(PageId,1,PAGE),add(SectionHandle,1,1)]));
        assert_eq!(l.sections.bytes,u64::MAX);
        assert_eq!(l.page_ids.bytes,0);
        assert!(l.invalid);
    }
    #[test]
    fn impossible_unique_balance_fails_closed() {
        let mut l = Ledger::default();
        assert!(!l.apply(&[add(UniqueShownPage,1,PAGE)]));
        assert_eq!(l.unique_shown.bytes,0);
        assert_eq!(l.alias_excess_bytes(),None);
    }
}
