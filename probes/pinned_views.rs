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
