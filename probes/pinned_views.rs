// SPDX-License-Identifier: GPL-3.0-or-later
//! Read plans pin backing objects, not mutable contents or GPU completion.
use std::{collections::BTreeMap, sync::Arc};

pub struct PinnedSpan<T> {
    pub section: Arc<T>,
    pub offset: usize,
    pub len: usize,
}

pub struct PinnedViews<T> {
    views: BTreeMap<usize, PinnedSpan<T>>,
}

impl<T> Default for PinnedViews<T> {
    fn default() -> Self { Self { views: BTreeMap::new() } }
}

impl<T> PinnedViews<T> {
    pub fn insert(&mut self, at: usize, len: usize, section: Arc<T>, offset: usize) -> bool {
        let Some(end) = at.checked_add(len) else { return false; };
        if len == 0 || offset.checked_add(len).is_none() { return false; }
        if self.views.range(..=at).next_back().is_some_and(|(&base, view)| base + view.len > at)
            || self.views.range(at..end).next().is_some()
        { return false; }
        self.views.insert(at, PinnedSpan { section, offset, len });
        true
    }

    // Host removes whole views. Partial requests are represented by
    // remove_exact followed by inserts for any restored neighboring views.
    pub fn remove_exact(&mut self, at: usize, len: usize) -> bool {
        if self.views.get(&at).is_none_or(|v| v.len != len) { return false; }
        self.views.remove(&at);
        true
    }

    // Returned Arcs keep native section objects alive after the index
    // changes; the caller must still synchronize all reads and writes.
    pub fn resolve(&self, address: usize, len: usize) -> Option<Vec<PinnedSpan<T>>> {
        let end = address.checked_add(len)?;
        let mut at = address;
        let mut plan: Vec<PinnedSpan<T>> = Vec::new();
        while at < end {
            let (&base, view) = self.views.range(..=at).next_back()?;
            let within = at - base;
            if within >= view.len { return None; }
            let count = (view.len - within).min(end - at);
            let offset = view.offset.checked_add(within)?;
            if let Some(last) = plan.last_mut()
                && Arc::ptr_eq(&last.section, &view.section)
                && last.offset.checked_add(last.len) == Some(offset)
            {
                last.len = last.len.checked_add(count)?;
            } else {
                plan.push(PinnedSpan { section: view.section.clone(), offset, len: count });
            }
            at += count;
        }
        Some(plan)
    }

    // Test-only contract: enumerate byte-exact aliases of a live section.
    // A complete answer is possible only for the mappings in this mirror;
    // the caller must hold the external mapping guard. Never truncate.
    #[cfg(test)]
    pub(super) fn aliases_for(&self, section: &Arc<T>, offset: usize, len: usize,
                   scan_limit: usize, alias_limit: usize) -> Option<Vec<(usize, usize)>> {
        let end = offset.checked_add(len)?;
        if len == 0 { return Some(Vec::new()); }
        if self.views.len() > scan_limit { return None; }
        let mut aliases = Vec::new();
        for (&base, view) in &self.views {
            if !Arc::ptr_eq(section, &view.section) { continue; }
            let view_end = view.offset.checked_add(view.len)?;
            let start = offset.max(view.offset);
            let stop = end.min(view_end);
            if start >= stop { continue; }
            if aliases.len() >= alias_limit { return None; }
            aliases.push((base.checked_add(start - view.offset)?, stop - start));
        }
        Some(aliases)
    }

    // Identity comparison, NOT a generation check or a data snapshot.
    // A mapping can change away and back; pending writes still matter.
    #[cfg(test)]
    pub(super) fn matches_plan(&self, address: usize, len: usize, plan: &[PinnedSpan<T>]) -> bool {
        self.resolve(address, len).is_some_and(|current| {
            current.len() == plan.len() && current.iter().zip(plan).all(|(a, b)|
                Arc::ptr_eq(&a.section, &b.section) && a.offset == b.offset && a.len == b.len)
        })
    }
}

#[cfg(test)]
mod pinned_view_tests {
    use super::*;
    #[test]
    fn plan_keeps_backing_alive_after_index_retirement() {
        let mut v = PinnedViews::default();
        let section = Arc::new(12);
        let weak = Arc::downgrade(&section);
        assert!(v.insert(100, 20, section.clone(), 0));
        let plan = v.resolve(105, 5).unwrap();
        assert!(v.remove_exact(100, 20));
        drop(section);
        assert!(weak.upgrade().is_some());
        assert_eq!(*plan[0].section, 12);
        drop(plan);
        assert!(weak.upgrade().is_none());
    }
    #[test]
    fn coalesces_only_identical_live_objects() {
        let mut v = PinnedViews::default();
        let a = Arc::new(7);
        let b = Arc::new(7);
        assert!(v.insert(10, 10, a.clone(), 0));
        assert!(v.insert(20, 10, a.clone(), 10));
        assert!(v.insert(30, 10, b.clone(), 20));
        let plan = v.resolve(15, 20).unwrap();
        assert_eq!(plan.len(), 2);
        assert_eq!((plan[0].offset, plan[0].len), (5, 15));
        assert_eq!((plan[1].offset, plan[1].len), (20, 5));
        assert!(Arc::ptr_eq(&plan[1].section, &b));
    }
    #[test]
    fn exact_remove_and_partial_reconstruction() {
        let mut v = PinnedViews::default();
        let a = Arc::new(1);
        assert!(v.insert(100, 30, a.clone(), 0));
        assert!(!v.remove_exact(110, 10));
        assert!(v.resolve(100, 30).is_some());
        assert!(v.remove_exact(100, 30));
        assert!(v.insert(100, 10, a.clone(), 0));
        assert!(v.insert(120, 10, a.clone(), 20));
        assert!(v.resolve(100, 30).is_none());
        assert_eq!(v.resolve(120, 10).unwrap()[0].offset, 20);
    }
    #[test]
    fn byte_alias_projection_is_complete_or_refuses() {
        let mut v = PinnedViews::default();
        let a = Arc::new(7);
        let b = Arc::new(7);
        assert!(v.insert(100, 20, a.clone(), 10));
        assert!(v.insert(200, 10, a.clone(), 20));
        assert!(v.insert(300, 20, b.clone(), 10));
        assert_eq!(v.aliases_for(&a, 18, 8, 3, 2), Some(vec![(108, 8), (200, 6)]));
        assert_eq!(v.aliases_for(&a, 18, 8, 3, 1), None);
        assert_eq!(v.aliases_for(&a, 18, 8, 2, 2), None);
        assert_eq!(v.aliases_for(&a, usize::MAX, 1, 3, 2), None);
        assert_eq!(v.aliases_for(&a, 30, 2, 3, 0), Some(vec![]));
        assert_eq!(v.aliases_for(&a, 0, 0, 0, 0), Some(vec![]));
        assert_eq!(v.aliases_for(&b, 18, 8, 3, 1), Some(vec![(308, 8)]));
    }

    #[test]
    fn alias_projection_matches_byte_oracle_even_for_many_views() {
        let mut v = PinnedViews::default();
        let a = Arc::new(1);
        let other = Arc::new(1);
        let mut oracle = Vec::new();
        for i in 0..80 {
            let base = i * 32;
            let offset = (i * 7) % 24;
            let section = if i % 7 == 0 { &other } else { &a };
            assert!(v.insert(base, 16, section.clone(), offset));
            if Arc::ptr_eq(section, &a) {
                oracle.extend((0..16).map(|k| (base + k, offset + k)));
            }
        }
        for offset in 0..42 {
            for len in 1..19 {
                let expected: Vec<_> = oracle.iter().filter(|(_, p)| *p >= offset && *p < offset+len)
                    .map(|(addr, _)| *addr).collect();
                let got: Vec<_> = v.aliases_for(&a, offset, len, 80, 80).unwrap()
                    .into_iter().flat_map(|(at,n)| at..at+n).collect();
                assert_eq!(got, expected);
            }
        }
        assert!(v.aliases_for(&a, 0, 40, 80, 32).is_none());
    }

    #[test]
    fn current_identity_does_not_follow_replaced_alias() {
        let mut v = PinnedViews::default();
        let a = Arc::new(7);
        let b = Arc::new(7);
        assert!(v.insert(100, 10, a.clone(), 0));
        let plan = v.resolve(100, 10).unwrap();
        assert!(v.matches_plan(100, 10, &plan));
        assert!(v.remove_exact(100, 10));
        assert!(!v.matches_plan(100, 10, &plan));
        assert!(v.insert(100, 10, b, 0));
        assert!(!v.matches_plan(100, 10, &plan));
        assert!(v.remove_exact(100, 10));
        assert!(v.insert(100, 5, a.clone(), 0));
        assert!(v.insert(105, 5, a, 5));
        // Same backing and byte offsets, despite different view partition.
        assert!(v.matches_plan(100, 10, &plan));
    }

    #[test]
    fn rejects_overlap_and_overflow_without_mutation() {
        let mut v = PinnedViews::default();
        let a = Arc::new(1);
        assert!(v.insert(100, 10, a.clone(), 0));
        assert!(!v.insert(99, 2, a.clone(), 0));
        assert!(!v.insert(105, 10, a.clone(), 0));
        assert!(!v.insert(usize::MAX, 1, a.clone(), 0));
        assert!(!v.insert(200, 1, a.clone(), usize::MAX));
        assert!(!v.insert(200, 0, a.clone(), 0));
        assert!(v.resolve(usize::MAX, 1).is_none());
        assert_eq!(v.resolve(100, 10).unwrap()[0].len, 10);
    }
}
