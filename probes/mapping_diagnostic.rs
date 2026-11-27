// SPDX-License-Identifier: GPL-3.0-or-later
//! Mapping diagnostic candidate: last completed publication only.
//! One externally serialized writer; readers never wait or retry.
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering::SeqCst};
const PAGE: u64 = 65536;
#[derive(Debug, PartialEq, Eq)]
pub(crate) struct Snapshot { pub(crate) generation: u64, pub(crate) view_bytes: u64, pub(crate) unique_pages: u64, pub(crate) alias_bytes: u64 }
#[derive(Debug, PartialEq, Eq)]
pub(crate) enum Unavailable { Disabled, Initial, Writing, Exhausted, Changed, Invalid }
#[derive(Default)]
pub(crate) struct Publication {
    sequence: AtomicU64,
    view_bytes: AtomicU64,
    unique_pages: AtomicU64,
    valid: AtomicBool,
    // Category-local loss of source knowledge cannot be cleared by later
    // plausible totals. This prototype has no reconstruction/reset path.
    uncertain: AtomicBool,
}
fn alias(view_bytes: u64, unique_pages: u64) -> Option<u64> {
    if view_bytes % PAGE != 0 { return None; }
    view_bytes.checked_sub(unique_pages.checked_mul(PAGE)?)
}
impl Publication {
    // The real producer MUST serialize all writers under the existing
    // PHYSICAL lock. This model does not acquire a new lock or spin.
    pub(crate) fn publish_serialized(&self, view_bytes: u64, unique_pages: u64, source_valid: bool) -> bool {
        let old = self.sequence.load(SeqCst);
        if old % 2 != 0 { return false; }
        let Some(next) = old.checked_add(2) else {
            // Permanent odd sentinel: never recycle an earlier generation.
            self.sequence.store(u64::MAX, SeqCst);
            return false;
        };
        self.sequence.store(old + 1, SeqCst);
        if !source_valid || alias(view_bytes, unique_pages).is_none() {
            self.uncertain.store(true, SeqCst);
        }
        self.view_bytes.store(view_bytes, SeqCst);
        self.unique_pages.store(unique_pages, SeqCst);
        self.valid.store(!self.uncertain.load(SeqCst), SeqCst);
        self.sequence.store(next, SeqCst);
        true
    }
    pub(crate) fn sample(&self) -> Result<Snapshot, Unavailable> {
        self.sample_with(|| {})
    }
    // Deterministic interleaving hook for tests; no production callbacks.
    fn sample_with(&self, between: impl FnOnce()) -> Result<Snapshot, Unavailable> {
        let first = self.sequence.load(SeqCst);
        if first == 0 { return Err(Unavailable::Initial); }
        if first == u64::MAX { return Err(Unavailable::Exhausted); }
        if first % 2 != 0 { return Err(Unavailable::Writing); }
        let view_bytes = self.view_bytes.load(SeqCst);
        between();
        let unique_pages = self.unique_pages.load(SeqCst);
        let valid = self.valid.load(SeqCst);
        let last = self.sequence.load(SeqCst);
        if first != last { return Err(Unavailable::Changed); }
        if !valid { return Err(Unavailable::Invalid); }
        let alias_bytes = alias(view_bytes, unique_pages).ok_or(Unavailable::Invalid)?;
        Ok(Snapshot { generation: first, view_bytes, unique_pages, alias_bytes })
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn initial_unavailable_then_empty_is_observed() {
        let p = Publication::default();
        assert_eq!(p.sample(), Err(Unavailable::Initial));
        assert!(p.publish_serialized(0,0,true));
        assert_eq!(p.sample(),Ok(Snapshot{generation:2,view_bytes:0,unique_pages:0,alias_bytes:0}));
    }
    #[test]
    fn coherent_pair_and_unchanged_generation() {
        let p = Publication::default();
        assert!(p.publish_serialized(3*PAGE,2,true));
        let s = Snapshot{generation:2,view_bytes:3*PAGE,unique_pages:2,alias_bytes:PAGE};
        assert_eq!(p.sample(),Ok(s));
        assert_eq!(p.sample().unwrap().generation,2);
        assert!(p.publish_serialized(PAGE,1,true));
        assert_eq!(p.sample().unwrap().generation,4);
    }
    #[test]
    fn odd_generation_is_not_read_or_retried() {
        let p = Publication::default();
        p.sequence.store(1,SeqCst);
        assert_eq!(p.sample_with(|| panic!("odd read should return")),Err(Unavailable::Writing));
    }
    #[test]
    fn interleaved_publication_discards_mixed_fields() {
        let p = Publication::default();
        assert!(p.publish_serialized(4*PAGE,2,true));
        assert_eq!(p.sample_with(|| { assert!(p.publish_serialized(2*PAGE,1,true)); }),Err(Unavailable::Changed));
        assert_eq!(p.sample().unwrap().alias_bytes,PAGE);
    }
    #[test]
    fn interleaved_odd_transition_is_rejected() {
        let p = Publication::default();
        assert!(p.publish_serialized(PAGE,1,true));
        assert_eq!(p.sample_with(|| p.sequence.store(3,SeqCst)),Err(Unavailable::Changed));
    }
    #[test]
    fn sequence_exhaustion_never_wraps_or_reuses() {
        let p = Publication::default();
        p.sequence.store(u64::MAX-3,SeqCst);
        assert!(p.publish_serialized(PAGE,1,true));
        assert_eq!(p.sample().unwrap().generation,u64::MAX-1);
        assert!(!p.publish_serialized(PAGE,1,true));
        assert_eq!(p.sequence.load(SeqCst),u64::MAX);
        assert!(!p.publish_serialized(0,0,true));
        assert_eq!(p.sample(),Err(Unavailable::Exhausted));
    }
    #[test]
    fn invalid_source_or_impossible_extents_suppress_alias() {
        for (bytes,pages,valid) in [(PAGE,1,false),(PAGE,2,true),(PAGE-1,0,true),(PAGE,u64::MAX,true)] {
            let p = Publication::default();
            assert!(p.publish_serialized(bytes,pages,valid));
            assert_eq!(p.sample(),Err(Unavailable::Invalid));
        }
    }
    #[test]
    fn unrelated_category_uncertainty_does_not_invalidate_mapping() {
        let mapping = Publication::default();
        let other = Publication::default(); // separate record, synthetic only
        assert!(mapping.publish_serialized(2*PAGE,1,true));
        assert!(other.publish_serialized(PAGE,1,false));
        assert_eq!(other.sample(),Err(Unavailable::Invalid));
        assert_eq!(mapping.sample().unwrap().alias_bytes,PAGE);
    }
    #[test]
    fn unknown_source_stays_invalid_after_plausible_publications() {
        let p = Publication::default();
        assert!(p.publish_serialized(2*PAGE,1,true));
        assert!(p.publish_serialized(2*PAGE,1,false));
        assert_eq!(p.sample(),Err(Unavailable::Invalid));
        assert!(p.publish_serialized(PAGE,1,true));
        assert_eq!(p.sample(),Err(Unavailable::Invalid));
        assert!(p.publish_serialized(0,0,true));
        assert_eq!(p.sample(),Err(Unavailable::Invalid));
        let q = Publication::default();
        assert!(q.publish_serialized(PAGE-1,0,true));
        assert!(q.publish_serialized(PAGE,1,true));
        assert_eq!(q.sample(),Err(Unavailable::Invalid));
    }
    #[test]
    fn real_writer_completes_between_reader_field_loads() {
        use std::sync::mpsc::sync_channel;
        use std::time::Duration;
        let p = Publication::default();
        assert!(p.publish_serialized(4*PAGE,2,true));
        let (entered_tx,entered_rx) = sync_channel(1);
        let (done_tx,done_rx) = sync_channel(1);
        std::thread::scope(|scope| {
            let p = &p;
            scope.spawn(move || {
                entered_rx.recv_timeout(Duration::from_secs(5)).unwrap();
                assert!(p.publish_serialized(2*PAGE,1,true));
                done_tx.send(()).unwrap();
            });
            assert_eq!(p.sample_with(|| {
                entered_tx.send(()).unwrap();
                done_rx.recv_timeout(Duration::from_secs(5)).unwrap();
            }),Err(Unavailable::Changed));
        });
        assert_eq!(p.sample().unwrap().alias_bytes,PAGE);
    }
    #[test]
    fn interrupted_writer_leaves_record_unavailable() {
        let p = Publication::default();
        assert!(p.publish_serialized(PAGE,1,true));
        std::thread::scope(|scope| {
            let writer = scope.spawn(|| {
                // Simulate an interruption between actual field stores.
                p.sequence.store(3,SeqCst);
                p.view_bytes.store(8*PAGE,SeqCst);
                panic!("synthetic publication interruption");
            });
            assert!(writer.join().is_err());
        });
        assert_eq!(p.sample(),Err(Unavailable::Writing));
        assert!(!p.publish_serialized(0,0,true));
        assert_eq!(p.sample(),Err(Unavailable::Writing));
    }
    #[test]
    fn bounded_concurrent_churn_never_accepts_inconsistent_pair() {
        use std::sync::Barrier;
        const N: u64 = 10_000;
        let p = Publication::default();
        let start = Barrier::new(2);
        let mut accepted = 0;
        let mut unavailable = 0;
        std::thread::scope(|scope| {
            scope.spawn(|| {
                start.wait();
                for n in 1..=N {
                    assert!(p.publish_serialized(n*2*PAGE,n,true));
                }
            });
            start.wait();
            for _ in 0..N {
                match p.sample() {
                    Ok(s) => {
                        assert_eq!(s.view_bytes,2*s.unique_pages*PAGE);
                        assert_eq!(s.alias_bytes,s.unique_pages*PAGE);
                        assert_eq!(s.generation,2*s.unique_pages);
                        accepted += 1;
                    },
                    Err(Unavailable::Initial | Unavailable::Writing | Unavailable::Changed) => unavailable += 1,
                    Err(other) => panic!("unexpected result {other:?}"),
                }
            }
        });
        assert_eq!(accepted+unavailable,N);
        assert_eq!(p.sample().unwrap().generation,2*N);
        // Scheduling is nondeterministic; neither population is required to
        // be nonzero. Forced overlap is tested separately above.
        println!("publication churn attempts={N} accepted={accepted} unavailable={unavailable}");
    }

}

#[derive(Default)]
pub(crate) struct Working {
    enabled: bool,
    attempted: bool,
    dirty: bool,
    unknown: bool,
    bytes: u64,
}
impl Working {
    pub(crate) fn new(enabled: bool) -> Self { Self { enabled, ..Default::default() } }
    pub(crate) fn begin(&mut self) { if self.enabled { self.attempted = true; } }
    pub(crate) fn unknown(&mut self) { if self.enabled { self.dirty = true; self.unknown = true; } }
    pub(crate) fn inserted(&mut self, bytes: usize, replaced: bool) {
        if !self.enabled { return; }
        self.dirty = true;
        if replaced || bytes == 0 || bytes as u64 % PAGE != 0 { self.unknown(); return; }
        if let Some(next) = self.bytes.checked_add(bytes as u64) { self.bytes = next; }
        else { self.unknown(); }
    }
    pub(crate) fn removed(&mut self, bytes: usize, removed: bool) {
        if !self.enabled { return; }
        self.dirty = true;
        if !removed || bytes == 0 || bytes as u64 % PAGE != 0 { self.unknown(); return; }
        if let Some(next) = self.bytes.checked_sub(bytes as u64) { self.bytes = next; }
        else { self.unknown(); }
    }
    pub(crate) fn needs_finish(&self) -> bool {
        self.enabled && (self.attempted || self.dirty)
    }
    // A known unchanged attempt does not create a new generation. An
    // interrupted attempt may have changed the host before bookkeeping.
    pub(crate) fn take_completed(&mut self, interrupted: bool) -> Option<(u64, bool)> {
        if !self.needs_finish() { return None; }
        let attempted = std::mem::take(&mut self.attempted);
        let dirty = std::mem::take(&mut self.dirty);
        if interrupted && (attempted || dirty) {
            self.unknown = true;
        } else if !dirty {
            return None;
        }
        Some((self.bytes, !self.unknown))
    }
    #[cfg(test)]
    fn finish(&mut self, unique: usize, interrupted: bool, publication: &Publication) {
        if let Some((bytes, valid)) = self.take_completed(interrupted) {
            publication.publish_serialized(bytes, unique as u64, valid);
        }
    }
}
#[cfg(test)]
mod working_tests {
    use super::*;
    #[test]
    fn disabled_does_not_publish() {
        let p = Publication::default();
        let mut w = Working::new(false);
        w.begin(); w.inserted(PAGE as usize,false); w.unknown(); w.removed(PAGE as usize,true);
        assert!(!w.needs_finish());
        w.finish(0,false,&p);
        assert_eq!(p.sample(),Err(Unavailable::Initial));
        assert_eq!(w.bytes,0);
    }
    #[test]
    fn dirty_transaction_and_read_only_boundary() {
        let p = Publication::default();
        let mut w = Working::new(true);
        w.finish(0,false,&p);
        assert_eq!(p.sample(),Err(Unavailable::Initial));
        w.begin(); w.inserted(2*PAGE as usize,false); w.inserted(PAGE as usize,false);
        w.finish(2,false,&p);
        assert_eq!(p.sample().unwrap().alias_bytes,PAGE);
        let generation=p.sample().unwrap().generation;
        w.finish(2,false,&p);
        assert_eq!(p.sample().unwrap().generation,generation);
        w.begin(); w.removed(2*PAGE as usize,true); w.finish(1,false,&p);
        assert_eq!(p.sample().unwrap().view_bytes,PAGE);
    }
    #[test]
    fn unknown_mutation_and_interruption_stay_invalid() {
        for interrupted in [false,true] {
            let p = Publication::default();
            let mut w = Working::new(true);
            w.begin(); w.inserted(PAGE as usize,false);
            if !interrupted { w.inserted(PAGE as usize,true); }
            w.finish(1,interrupted,&p);
            assert_eq!(p.sample(),Err(Unavailable::Invalid));
            w.removed(PAGE as usize,true); w.finish(0,false,&p);
            assert_eq!(p.sample(),Err(Unavailable::Invalid));
        }
    }
    #[test]
    fn known_unchanged_attempt_does_not_publish() {
        let p = Publication::default();
        let mut w = Working::new(true);
        assert!(!w.needs_finish());
        w.begin();
        assert!(w.needs_finish());
        w.finish(0,false,&p);
        assert_eq!(p.sample(),Err(Unavailable::Initial));
        assert!(!w.needs_finish());
        w.begin(); w.inserted(PAGE as usize,false); w.finish(1,false,&p);
        let old = p.sample().unwrap();
        w.begin(); w.finish(1,false,&p);
        assert_eq!(p.sample(),Ok(old));
        assert!(!w.needs_finish());
    }
    #[test]
    fn interruption_before_bookkeeping_is_sticky() {
        let p = Publication::default();
        let mut w = Working::new(true);
        w.begin(); w.finish(0,true,&p);
        assert_eq!(p.sample(),Err(Unavailable::Invalid));
        assert!(!w.needs_finish());
        w.begin(); w.inserted(PAGE as usize,false); w.finish(1,false,&p);
        assert_eq!(p.sample(),Err(Unavailable::Invalid));
    }
    #[test]
    fn read_only_interruption_does_not_create_publication() {
        let p = Publication::default();
        let mut w = Working::new(true);
        assert!(!w.needs_finish());
        w.finish(0,true,&p);
        assert_eq!(p.sample(),Err(Unavailable::Initial));
    }

}
