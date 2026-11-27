// SPDX-License-Identifier: GPL-3.0-or-later
//! Bounded, conservative range invalidation model, NOT a memory access guard.
//! Call under an external lock that serializes snapshots and mutation events.
use std::{collections::BTreeMap, sync::Arc};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Span { start: usize, end: usize }

impl Span {
    pub fn new(start: usize, len: usize) -> Option<Self> {
        let end = start.checked_add(len)?;
        (end > start).then_some(Self { start, end })
    }
}

#[derive(Clone, Copy)]
struct Entry { end: usize, generation: u64 }

pub struct Token {
    domain: Arc<()>,
    span: Span,
    generation: u64,
}

pub struct Generations {
    domain: Arc<()>,
    generation: u64,
    floor: u64,
    exhausted: bool,
    limit: usize,
    ranges: BTreeMap<usize, Entry>,
}

impl Default for Generations {
    fn default() -> Self { Self::new(4096) }
}

impl Generations {
    pub fn new(limit: usize) -> Self {
        Self {
            domain: Arc::new(()), generation: 0, floor: 0,
            exhausted: false, limit, ranges: BTreeMap::new(),
        }
    }

    pub fn snapshot(&self, span: Span) -> Option<Token> {
        (!self.exhausted).then(|| Token {
            domain: self.domain.clone(), span, generation: self.generation,
        })
    }

    pub fn valid(&self, token: &Token) -> bool {
        if self.exhausted || !Arc::ptr_eq(&self.domain, &token.domain)
            || token.generation < self.floor || token.generation > self.generation
        { return false; }
        let Span { start, end } = token.span;
        // At most one preceding interval can intersect; all subsequent
        // intervals are disjoint and sorted. Adjacent ranges do not overlap.
        if self.ranges.range(..start).next_back().is_some_and(|(_, e)|
            e.end > start && e.generation > token.generation)
        { return false; }
        !self.ranges.range(start..end).any(|(_, e)| e.generation > token.generation)
    }

    fn advance(&mut self) -> Option<u64> {
        if self.exhausted { return None; }
        match self.generation.checked_add(1) {
            Some(next) => { self.generation = next; Some(next) }
            None => {
                // Never reuse a version, even if all old intervals disappear.
                self.exhausted = true;
                self.ranges.clear();
                None
            }
        }
    }

    // Unknown writer footprint, lost metadata, or capacity pressure must
    // invalidate every earlier token, never silently forget an invalidation.
    pub fn invalidate_all(&mut self) -> bool {
        let Some(epoch) = self.advance() else { return false; };
        self.reset_at(epoch);
        true
    }

    fn reset_at(&mut self, generation: u64) {
        self.floor = generation;
        self.ranges.clear();
    }

    // A single mutation may affect multiple disjoint virtual ranges
    // (for example, a backing write through aliases). All get one epoch.
    // The caller supplies COMPLETE affected spans, not just requested bytes.
    pub fn mark(&mut self, spans: &[Span]) -> bool {
        if spans.is_empty() { return !self.exhausted; }
        let Some(epoch) = self.advance() else { return false; };
        for &span in spans {
            self.mark_one(span, epoch);
            if self.ranges.len() > self.limit {
                // Reset already covers this entire logical event, including
                // spans not yet processed. Future tokens are acquired only
                // after this method returns under the external lock.
                self.reset_at(epoch);
                break;
            }
        }
        true
    }

    fn mark_one(&mut self, span: Span, generation: u64) {
        let Span { mut start, mut end } = span;
        // Save unaffected fragments of old intervals with their old epochs.
        if let Some((&base, &old)) = self.ranges.range(..start).next_back() {
            if old.end > start {
                self.ranges.remove(&base);
                self.ranges.insert(base, Entry { end: start, ..old });
                if old.end > end {
                    self.ranges.insert(end, old);
                }
            }
        }
        let hit: Vec<_> = self.ranges.range(start..end)
            .map(|(&base, &entry)| (base, entry)).collect();
        for (base, old) in hit {
            self.ranges.remove(&base);
            if old.end > end { self.ranges.insert(end, old); }
        }
        // Merge only adjacent intervals from this exact mutation epoch.
        if let Some((&base, &old)) = self.ranges.range(..start).next_back() {
            if old.end == start && old.generation == generation {
                self.ranges.remove(&base);
                start = base;
            }
        }
        if let Some(&old) = self.ranges.get(&end) {
            if old.generation == generation {
                self.ranges.remove(&end);
                end = old.end;
            }
        }
        self.ranges.insert(start, Entry { end, generation });
    }
}

#[cfg(test)]
mod range_generation_tests {
    use super::*;
    fn s(at: usize, len: usize) -> Span { Span::new(at, len).unwrap() }

    #[test]
    fn disjoint_tokens_survive_adjacent_changes() {
        let mut g = Generations::default();
        let a = g.snapshot(s(0, 64)).unwrap();
        let b = g.snapshot(s(64, 64)).unwrap();
        assert!(g.mark(&[s(64, 64)]));
        assert!(g.valid(&a));
        assert!(!g.valid(&b));
        let fresh = g.snapshot(s(64, 64)).unwrap();
        assert!(g.valid(&fresh));
        assert!(g.mark(&[s(128, 1)]));
        assert!(g.valid(&fresh));
        assert!(Span::new(0, 0).is_none());
        assert!(Span::new(usize::MAX, 1).is_none());
    }

    #[test]
    fn split_preserves_old_generations_outside_new_write() {
        let mut g = Generations::default();
        let old = g.snapshot(s(0, 100)).unwrap();
        g.mark(&[s(0, 100)]);
        let left = g.snapshot(s(0, 40)).unwrap();
        let right = g.snapshot(s(60, 40)).unwrap();
        let middle = g.snapshot(s(40, 20)).unwrap();
        g.mark(&[s(40, 20)]);
        assert!(!g.valid(&old));
        assert!(g.valid(&left));
        assert!(g.valid(&right));
        assert!(!g.valid(&middle));
        assert_eq!(g.ranges.len(), 3);
    }

    #[test]
    fn alias_event_marks_disjoint_ranges_and_merges_same_epoch() {
        let mut g = Generations::default();
        let a = g.snapshot(s(10, 10)).unwrap();
        let b = g.snapshot(s(100, 20)).unwrap();
        let c = g.snapshot(s(20, 80)).unwrap();
        g.mark(&[s(10, 10), s(110, 10), s(100, 10)]);
        assert!(!g.valid(&a));
        assert!(!g.valid(&b));
        assert!(g.valid(&c));
        assert_eq!(g.ranges.len(), 2);
    }

    #[test]
    fn capacity_reset_invalidates_all_previous_tokens() {
        let mut g = Generations::new(2);
        let unrelated = g.snapshot(s(500, 1)).unwrap();
        g.mark(&[s(0, 1), s(2, 1), s(4, 1), s(6, 1)]);
        assert!(g.ranges.is_empty());
        assert!(!g.valid(&unrelated));
        let fresh = g.snapshot(s(500, 1)).unwrap();
        g.mark(&[s(0, 1)]);
        assert!(g.valid(&fresh));
        assert!(g.invalidate_all());
        assert!(!g.valid(&fresh));
        let mut zero = Generations::new(0);
        let t = zero.snapshot(s(500, 1)).unwrap();
        zero.mark(&[s(0, 1)]);
        assert!(!zero.valid(&t));
        assert!(zero.ranges.is_empty());
    }

    #[test]
    fn foreign_tokens_and_epoch_exhaustion_fail_closed() {
        let mut g = Generations::default();
        let other = Generations::default();
        let t = other.snapshot(s(0, 1)).unwrap();
        assert!(!g.valid(&t));
        g.generation = u64::MAX - 1;
        let older = g.snapshot(s(0, 1)).unwrap();
        assert!(g.mark(&[s(1, 1)]));
        assert!(g.valid(&older));
        let last = g.snapshot(s(0, 1)).unwrap();
        assert!(!g.invalidate_all());
        assert!(!g.valid(&last));
        assert!(g.snapshot(s(0, 1)).is_none());
        assert!(!g.mark(&[s(0, 1)]));
    }

    #[test]
    fn deterministic_dense_oracle() {
        let mut g = Generations::new(128);
        let mut dense = [0u64; 32];
        let mut tokens = Vec::new();
        let mut seed = 29u32;
        for _ in 0..300 {
            for start in 0..32 {
                let len = (32-start).min(5);
                tokens.push((g.snapshot(s(start, len)).unwrap(), start, len, g.generation));
            }
            seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
            let start = ((seed >> 8) % 32) as usize;
            let len = (1 + ((seed >> 16) % 8) as usize).min(32-start);
            assert!(g.mark(&[s(start, len)]));
            dense[start..start+len].fill(g.generation);
            for (token, at, n, epoch) in &tokens {
                let expected = dense[*at..*at+*n].iter().all(|v| *v <= *epoch);
                assert_eq!(g.valid(token), expected);
            }
            // Every represented range remains disjoint and well formed.
            let mut last = 0;
            for (&start, entry) in &g.ranges {
                assert!(start >= last && start < entry.end);
                last = entry.end;
            }
            assert_eq!(g.floor, 0);
        }
    }
}
