// SPDX-License-Identifier: GPL-3.0-or-later
//! Deliberately conservative lifetime model, NOT actual descriptor or GPU code.
//! Retaining all replaced slot versions is a safety upper bound, not an
//! optimization; production needs actual descriptor visibility and retire proof.
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex, Weak};

#[derive(Debug, PartialEq, Eq)]
enum Error { Occupied, UnknownOwner, Overflow, Busy, WrongDomain, NotComplete, Quarantined, UnknownFlight }

struct Heap<T> {
    id: u64,
    slots: Mutex<BTreeMap<u32, Arc<T>>>,
    old_slots: Mutex<Vec<Arc<T>>>,
}
impl<T> Heap<T> {
    fn replace(&self, slot: u32, resource: Arc<T>) {
        let mut slots = self.slots.lock().unwrap();
        if let Some(old) = slots.insert(slot, resource) {
            // Keep every possible earlier version until the modeled owner
            // dies. No assumption that descriptor contents are immutable
            // during recording, submission, replay or execution.
            self.old_slots.lock().unwrap().push(old);
        }
    }
}

struct Registry<T> {
    next: u64,
    live: BTreeMap<usize, Weak<Heap<T>>>,
}
impl<T> Registry<T> {
    fn new() -> Self { Self { next: 1, live: BTreeMap::new() } }
    fn create(&mut self, address: usize) -> Result<Arc<Heap<T>>, Error> {
        // A title wrapper can be destroyed while its separately retained
        // backing state remains alive. Its address can then be reused.
        if self.live.contains_key(&address) { return Err(Error::Occupied); }
        let id = self.next;
        self.next = self.next.checked_add(1).ok_or(Error::Overflow)?;
        let heap = Arc::new(Heap { id, slots: Mutex::new(BTreeMap::new()), old_slots: Mutex::new(Vec::new()) });
        self.live.insert(address, Arc::downgrade(&heap));
        Ok(heap)
    }
    fn unregister(&mut self, address: usize, heap: &Arc<Heap<T>>) -> Result<(), Error> {
        if !self.live.get(&address).is_some_and(|w| Weak::ptr_eq(w, &Arc::downgrade(heap))) {
            return Err(Error::UnknownOwner);
        }
        self.live.remove(&address);
        Ok(())
    }
}

// Keep the original global pass serialization in this model. Keys are
// stable owner IDs, not recyclable wrapper addresses. Weak entries do
// not confer ownership and are pruned only when no real owner remains.
struct PassCache<T> {
    entries: Mutex<BTreeMap<u64, Weak<Heap<T>>>>,
}
impl<T> PassCache<T> {
    fn new() -> Self { Self { entries: Mutex::new(BTreeMap::new()) } }
    fn visit(&self, owner: &Arc<Heap<T>>, work: impl FnOnce()) {
        let mut entries = self.entries.lock().unwrap();
        entries.insert(owner.id, Arc::downgrade(owner));
        work();
    }
    fn prune(&self) {
        self.entries.lock().unwrap().retain(|_, w| w.strong_count() != 0);
    }
}

// Actual command lists must acquire ownership at every bind/consumption
// site, including dynamic indexing and skipped refresh. This is a model
// assertion of that contract, not evidence that current HostList does so.
struct Recorded<T> {
    owners: BTreeMap<u64, Arc<Heap<T>>>,
}
struct List<T> {
    recorded: Arc<Recorded<T>>,
}
impl<T> List<T> {
    fn new() -> Self { Self { recorded: Arc::new(Recorded { owners: BTreeMap::new() }) } }
    fn bind(&mut self, heap: &Arc<Heap<T>>, _refresh_skipped: bool) -> Result<(), Error> {
        // Refresh eligibility does not control the retention token.
        let rec = Arc::get_mut(&mut self.recorded).ok_or(Error::Busy)?;
        rec.owners.entry(heap.id).or_insert_with(|| heap.clone());
        Ok(())
    }
    fn reset(&mut self) -> Result<(), Error> {
        // A replay keeps the original recording alive. Refuse reset until
        // the final submitted flight retires, even if the title wrapper died.
        if Arc::strong_count(&self.recorded) != 1 { return Err(Error::Busy); }
        self.recorded = Arc::new(Recorded { owners: BTreeMap::new() });
        Ok(())
    }
}

#[derive(Clone)]
struct Domain(Arc<()>);
impl Domain { fn new() -> Self { Self(Arc::new(())) } }
struct Flight<T> {
    _recorded: Arc<Recorded<T>>,
    completed: bool,
    quarantined: bool,
}
struct Queue<T> {
    domain: Domain,
    next: u64,
    active: BTreeMap<u64, Flight<T>>,
    lost: bool,
}
impl<T> Queue<T> {
    fn new() -> Self { Self { domain: Domain::new(), next: 1, active: BTreeMap::new(), lost: false } }
    fn submit(&mut self, list: &List<T>) -> Result<u64, Error> {
        if self.lost { return Err(Error::Quarantined); }
        let fence = self.next;
        if fence == u64::MAX { return Err(Error::Overflow); }
        self.next += 1;
        self.active.insert(fence, Flight { _recorded: list.recorded.clone(), completed: false, quarantined: false });
        Ok(fence)
    }
    fn complete(&mut self, domain: &Domain, value: u64) -> Result<(), Error> {
        if !Arc::ptr_eq(&self.domain.0, &domain.0) { return Err(Error::WrongDomain); }
        if value == u64::MAX {
            self.lost = true;
            for f in self.active.values_mut() { f.quarantined = true; }
            return Err(Error::Quarantined);
        }
        if self.lost { return Err(Error::Quarantined); }
        if value >= self.next { return Err(Error::UnknownFlight); }
        for (_, f) in self.active.range_mut(..=value) { f.completed = true; }
        Ok(())
    }
    fn retire(&mut self, fence: u64, publish: impl FnOnce() -> bool) -> Result<(), Error> {
        let f = self.active.get_mut(&fence).ok_or(Error::UnknownFlight)?;
        if f.quarantined { return Err(Error::Quarantined); }
        if !f.completed { return Err(Error::NotComplete); }
        // Treat false or unwind as uncertain side effects. No blind retry.
        f.quarantined = true;
        if !publish() { return Err(Error::Quarantined); }
        self.active.remove(&fence);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn recorded_unsubmitted_and_skipped_refresh_keep_owner() {
        let mut registry = Registry::new();
        let heap = registry.create(10).unwrap();
        let resource = Arc::new(1);
        let weak = Arc::downgrade(&resource);
        heap.replace(0,resource);
        let mut first = List::new();
        let mut skipped = List::new();
        first.bind(&heap,false).unwrap();
        skipped.bind(&heap,true).unwrap();
        registry.unregister(10,&heap).unwrap();
        drop(heap);
        first.reset().unwrap();
        assert!(weak.upgrade().is_some());
        skipped.reset().unwrap();
        assert!(weak.upgrade().is_none());
    }
    #[test]
    fn address_reuse_does_not_inherit_or_unregister_old_owner() {
        let mut registry = Registry::<u32>::new();
        let old = registry.create(42).unwrap();
        let cache = PassCache::new();
        cache.visit(&old,||{});
        let mut list = List::new();
        list.bind(&old,true).unwrap();
        registry.unregister(42,&old).unwrap();
        let new = registry.create(42).unwrap();
        assert_ne!(old.id,new.id);
        assert!(new.slots.lock().unwrap().is_empty());
        assert_eq!(registry.unregister(42,&old),Err(Error::UnknownOwner));
        cache.visit(&new,||{});
        drop(old);
        cache.prune();
        assert_eq!(cache.entries.lock().unwrap().len(),2);
        list.reset().unwrap();
        cache.prune();
        assert_eq!(cache.entries.lock().unwrap().len(),1);
        assert!(cache.entries.lock().unwrap().contains_key(&new.id));
    }
    #[test]
    fn replaced_slot_versions_survive_recording_and_execution() {
        let mut registry = Registry::new();
        let heap = registry.create(7).unwrap();
        let a = Arc::new(1);
        let wa = Arc::downgrade(&a);
        heap.replace(5,a);
        let mut list = List::new();
        list.bind(&heap,true).unwrap();
        let b = Arc::new(2);
        let wb = Arc::downgrade(&b);
        heap.replace(5,b);
        let mut q = Queue::new();
        let f = q.submit(&list).unwrap();
        let c = Arc::new(3);
        let wc = Arc::downgrade(&c);
        heap.replace(5,c);
        registry.unregister(7,&heap).unwrap();
        drop(heap);
        assert_eq!(list.reset(),Err(Error::Busy));
        assert!(wa.upgrade().is_some() && wb.upgrade().is_some() && wc.upgrade().is_some());
        let d = q.domain.clone();
        q.complete(&d,f).unwrap();
        q.retire(f,||true).unwrap();
        assert!(wa.upgrade().is_some() && wb.upgrade().is_some() && wc.upgrade().is_some());
        list.reset().unwrap();
        assert!(wa.upgrade().is_none() && wb.upgrade().is_none() && wc.upgrade().is_none());
    }
    #[test]
    fn multiple_replays_require_all_completions_and_publication() {
        let mut registry = Registry::<u32>::new();
        let heap = registry.create(9).unwrap();
        let weak = Arc::downgrade(&heap);
        let mut list = List::new();
        list.bind(&heap,true).unwrap();
        let mut q = Queue::new();
        let a = q.submit(&list).unwrap();
        let b = q.submit(&list).unwrap();
        registry.unregister(9,&heap).unwrap();
        drop(heap);
        assert_eq!(q.retire(a,||panic!("early publish")),Err(Error::NotComplete));
        assert_eq!(q.complete(&Domain::new(),b),Err(Error::WrongDomain));
        let d = q.domain.clone();
        q.complete(&d,a).unwrap();
        q.retire(a,||true).unwrap();
        assert_eq!(list.reset(),Err(Error::Busy));
        q.complete(&d,b).unwrap();
        assert_eq!(list.reset(),Err(Error::Busy));
        q.retire(b,||true).unwrap();
        // Completed recordings are still replayable until reset.
        assert!(weak.upgrade().is_some());
        let c = q.submit(&list).unwrap();
        q.complete(&d,c).unwrap();
        q.retire(c,||true).unwrap();
        list.reset().unwrap();
        assert!(weak.upgrade().is_none());
    }
    #[test]
    fn dropping_recording_after_submit_retains_flight_owner() {
        let mut registry = Registry::<u32>::new();
        let heap = registry.create(1).unwrap();
        let weak = Arc::downgrade(&heap);
        let mut list = List::new();
        list.bind(&heap,true).unwrap();
        let mut q = Queue::new();
        let f = q.submit(&list).unwrap();
        registry.unregister(1,&heap).unwrap();
        drop(heap);
        drop(list);
        assert!(weak.upgrade().is_some());
        let d = q.domain.clone();
        q.complete(&d,f).unwrap();
        assert!(weak.upgrade().is_some());
        q.retire(f,||true).unwrap();
        assert!(weak.upgrade().is_none());
    }
    #[test]
    fn device_loss_and_uncertain_publication_retain_active_owners() {
        for lost in [false,true] {
            let mut registry = Registry::<u32>::new();
            let heap = registry.create(3).unwrap();
            let weak = Arc::downgrade(&heap);
            let mut list = List::new();
            list.bind(&heap,true).unwrap();
            let mut q = Queue::new();
            let f = q.submit(&list).unwrap();
            registry.unregister(3,&heap).unwrap();
            drop(heap);
            drop(list);
            let d = q.domain.clone();
            if lost {
                assert_eq!(q.complete(&d,u64::MAX),Err(Error::Quarantined));
                assert_eq!(q.submit(&List::new()),Err(Error::Quarantined));
            } else {
                q.complete(&d,f).unwrap();
                assert_eq!(q.retire(f,||false),Err(Error::Quarantined));
            }
            assert_eq!(q.retire(f,||panic!("uncertain replay")),Err(Error::Quarantined));
            assert!(weak.upgrade().is_some());
            // Test teardown is not an approved production device-loss recovery.
        }
    }
    #[test]
    fn panic_in_publication_does_not_release_or_replay() {
        let mut registry = Registry::<u32>::new();
        let heap = registry.create(1).unwrap();
        let weak = Arc::downgrade(&heap);
        let mut list = List::new();
        list.bind(&heap,true).unwrap();
        let mut q = Queue::new();
        let f = q.submit(&list).unwrap();
        registry.unregister(1,&heap).unwrap();
        drop(heap);
        drop(list);
        let d = q.domain.clone();
        q.complete(&d,f).unwrap();
        assert!(std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _ = q.retire(f,||panic!("partial publication"));
        })).is_err());
        assert_eq!(q.retire(f,||panic!("replay")),Err(Error::Quarantined));
        assert!(weak.upgrade().is_some());
    }
    #[test]
    fn concurrent_heap_passes_keep_global_serialization() {
        use std::sync::atomic::{AtomicUsize, Ordering};
        let mut registry = Registry::<u32>::new();
        let a = registry.create(1).unwrap();
        let b = registry.create(2).unwrap();
        let cache = PassCache::new();
        let active = AtomicUsize::new(0);
        std::thread::scope(|s| {
            for h in [&a,&b] {
                let cache = &cache;
                let active = &active;
                s.spawn(move || {
                    for _ in 0..100 {
                        cache.visit(h,||{
                            assert_eq!(active.fetch_add(1,Ordering::SeqCst),0);
                            std::thread::yield_now();
                            assert_eq!(active.fetch_sub(1,Ordering::SeqCst),1);
                        });
                    }
                });
            }
        });
        assert_eq!(cache.entries.lock().unwrap().len(),2);
    }
}
