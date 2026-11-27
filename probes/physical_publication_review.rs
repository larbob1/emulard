// SPDX-License-Identifier: GPL-3.0-or-later
//! Standalone review model, not runtime instrumentation.
//! One externally serialized writer; readers never wait or retry.
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering::SeqCst};
const PAGE: u64 = 65536;
#[derive(Debug, PartialEq, Eq)]
struct Snapshot { generation: u64, view_bytes: u64, unique_pages: u64, alias_bytes: u64 }
#[derive(Debug, PartialEq, Eq)]
enum Unavailable { Initial, WritingOrExhausted, Changed, Invalid }
#[derive(Default)]
struct Publication {
    sequence: AtomicU64,
    view_bytes: AtomicU64,
    unique_pages: AtomicU64,
    valid: AtomicBool,
}
fn alias(view_bytes: u64, unique_pages: u64) -> Option<u64> {
    if view_bytes % PAGE != 0 { return None; }
    view_bytes.checked_sub(unique_pages.checked_mul(PAGE)?)
}
impl Publication {
    // The real producer MUST serialize all writers under the existing
    // PHYSICAL lock. This model does not acquire a new lock or spin.
    fn publish_serialized(&self, view_bytes: u64, unique_pages: u64, source_valid: bool) -> bool {
        let old = self.sequence.load(SeqCst);
        if old % 2 != 0 { return false; }
        let Some(next) = old.checked_add(2) else {
            // Permanent odd sentinel: never recycle an earlier generation.
            self.sequence.store(u64::MAX, SeqCst);
            return false;
        };
        self.sequence.store(old + 1, SeqCst);
        self.view_bytes.store(view_bytes, SeqCst);
        self.unique_pages.store(unique_pages, SeqCst);
        self.valid.store(source_valid && alias(view_bytes, unique_pages).is_some(), SeqCst);
        self.sequence.store(next, SeqCst);
        true
    }
    fn sample(&self) -> Result<Snapshot, Unavailable> {
        self.sample_with(|| {})
    }
    // Deterministic interleaving hook for tests; no production callbacks.
    fn sample_with(&self, between: impl FnOnce()) -> Result<Snapshot, Unavailable> {
        let first = self.sequence.load(SeqCst);
        if first == 0 { return Err(Unavailable::Initial); }
        if first % 2 != 0 { return Err(Unavailable::WritingOrExhausted); }
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
        assert_eq!(p.sample_with(|| panic!("odd read should return")),Err(Unavailable::WritingOrExhausted));
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
        assert_eq!(p.sample(),Err(Unavailable::WritingOrExhausted));
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
}
