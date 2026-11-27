// SPDX-License-Identifier: GPL-3.0-or-later
//! Serial ownership model, not a D3D12 descriptor heap or a fence proof.
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

#[derive(Default)]
struct Owner<T> {
    pass_ranges: Mutex<(u64, HashMap<u32, (Arc<T>, u64, u64)>)>,
}

impl<T> Owner<T> {
    fn record(&self, slot: u32, item: Arc<T>, start: u64, end: u64) {
        let mut kept = self.pass_ranges.lock().unwrap();
        kept.0 += 1;
        kept.1.insert(slot, (item,start,end));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn dropping_owner_releases_its_cache_only() {
        let owner = Owner::default();
        let shadow = Arc::new(7);
        let weak = Arc::downgrade(&shadow);
        owner.record(3, shadow.clone(), 0, 8);
        drop(shadow);
        assert!(weak.upgrade().is_some());
        drop(owner);
        assert!(weak.upgrade().is_none());
    }

    #[test]
    fn independent_list_pin_survives_owner_drop() {
        let owner = Owner::default();
        let list = Arc::new(7);
        let weak = Arc::downgrade(&list);
        owner.record(3,list.clone(),0,8);
        drop(owner);
        assert_eq!(Arc::strong_count(&list),1);
        drop(list);
        assert!(weak.upgrade().is_none());
    }

    #[test]
    fn new_heap_does_not_inherit_old_pass_count_or_slots() {
        let owner = Owner::default();
        owner.record(0,Arc::new(1),0,4);
        drop(owner);
        let new = Owner::<i32>::default();
        let kept = new.pass_ranges.lock().unwrap();
        assert_eq!(kept.0,0);
        assert!(kept.1.is_empty());
    }

    #[test]
    fn separate_live_owner_and_slot_replacement_keep_correct_refs() {
        let a = Owner::default();
        let b = Owner::default();
        let old = Arc::new(1);
        let weak = Arc::downgrade(&old);
        a.record(4,old.clone(),0,4);
        b.record(4,old,0,4);
        a.record(4,Arc::new(2),0,4);
        drop(a);
        assert!(weak.upgrade().is_some());
        assert_eq!(*b.pass_ranges.lock().unwrap().1.get(&4).unwrap().0,1);
        drop(b);
        assert!(weak.upgrade().is_none());
    }
}
