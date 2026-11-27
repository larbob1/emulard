// SPDX-License-Identifier: GPL-3.0-or-later
//! Advisory exact placeholder hints. Never a source of mapping authority.
use std::collections::BTreeMap;

const MAX_HINTS: usize = 65_536;

#[derive(Default)]
pub(super) struct ExactHints {
    // Nonoverlapping ranges; values are exclusive ends.
    ranges: BTreeMap<usize, usize>,
}

impl ExactHints {
    pub(super) fn contains(&self, at: usize, len: usize) -> bool {
        len != 0 && at.checked_add(len).is_some_and(|end| self.ranges.get(&at) == Some(&end))
    }

    pub(super) fn discard(&mut self, at: usize, len: usize) {
        if len == 0 { return; }
        let Some(end) = at.checked_add(len) else {
            self.ranges.clear();
            return;
        };
        // At most one predecessor can overlap a nonoverlapping range.
        if let Some((&start, &last)) = self.ranges.range(..at).next_back()
            && last > at
        {
            self.ranges.remove(&start);
        }
        // Remove overlapping hints entirely; never invent a split.
        let hit: Vec<_> = self.ranges.range(at..end).map(|(&start, _)| start).collect();
        for start in hit { self.ranges.remove(&start); }
    }

    pub(super) fn take(&mut self, at: usize, len: usize) -> bool {
        // With nonoverlapping intervals, an exact hit has no other
        // intersecting hints. Avoid the predecessor/range scan and hit Vec.
        if self.contains(at, len) {
            self.ranges.remove(&at);
            return true;
        }
        self.discard(at, len);
        false
    }

    pub(super) fn record(&mut self, at: usize, len: usize) {
        // Recording an already exact interval is idempotent, even at cap.
        if self.contains(at, len) { return; }
        self.discard(at, len);
        if len == 0 || self.ranges.len() >= MAX_HINTS { return; }
        if let Some(end) = at.checked_add(len) {
            self.ranges.insert(at, end);
        }
    }
}

#[cfg(test)]
mod placeholder_hint_tests {
    use super::*;
    #[test]
    fn exact_take_preserves_neighbors() {
        let mut h = ExactHints::default();
        h.record(10, 20);
        h.record(30, 10);
        assert!(h.take(10, 20));
        assert!(!h.take(10, 20));
        assert!(h.contains(30, 10));
    }
    #[test]
    fn partial_overlap_never_invents_split_or_union() {
        let mut h = ExactHints::default();
        h.record(10, 20);
        h.record(30, 10);
        h.record(40, 10);
        assert!(!h.take(20, 15));
        assert!(!h.contains(10, 20));
        assert!(!h.contains(10, 10));
        assert!(!h.contains(30, 10));
        assert!(h.contains(40, 10));
        h.record(50, 10);
        assert!(!h.contains(40, 20));
    }
    #[test]
    fn replacement_and_overflow() {
        let mut h = ExactHints::default();
        h.record(10, 10);
        h.record(12, 2);
        assert!(!h.contains(10, 10));
        assert!(h.contains(12, 2));
        h.record(usize::MAX, 2);
        assert!(h.ranges.is_empty());
        h.record(10, 0);
        assert!(!h.contains(10, 0));
    }
    #[test]
    fn exact_repeat_and_mismatched_take() {
        let mut h = ExactHints::default();
        h.record(0, 10);
        h.record(10, 10);
        h.record(20, 10);
        for _ in 0..64 { h.record(10, 10); }
        assert_eq!(h.ranges.len(), 3);
        assert!(h.take(10, 10));
        assert!(h.contains(0, 10));
        assert!(h.contains(20, 10));
        h.record(10, 10);
        // Same start but wrong size must still invalidate all overlaps.
        assert!(!h.take(10, 15));
        assert!(h.contains(0, 10));
        assert!(!h.contains(10, 10));
        assert!(!h.contains(20, 10));
    }

    #[test]
    fn exact_fast_paths_match_reference_interval_operations() {
        let mut h = ExactHints::default();
        let mut reference = BTreeMap::new();
        let mut seed = 0x5eeda11u32;
        for step in 0..4096 {
            seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
            let at = ((seed >> 8) % 128) as usize;
            let len = ((seed >> 16) % 17) as usize;
            let end = at + len;
            let exact = len != 0 && reference.get(&at) == Some(&end);
            if len != 0 {
                reference.retain(|&start, last| *last <= at || start >= end);
            }
            match step % 3 {
                0 => {
                    h.record(at, len);
                    if len != 0 { reference.insert(at, end); }
                }
                1 => assert_eq!(h.take(at, len), exact),
                _ => h.discard(at, len),
            }
            assert_eq!(h.ranges, reference);
        }
    }

    #[test]
    fn bounded_cache() {
        let mut h = ExactHints::default();
        for k in 0..MAX_HINTS+8 { h.record(k*2, 1); }
        assert_eq!(h.ranges.len(), MAX_HINTS);
        h.record(0, 1);
        assert_eq!(h.ranges.len(), MAX_HINTS);
        assert!(h.contains(0, 1));
        assert!(!h.contains(MAX_HINTS*2, 1));
        assert!(h.take(0, 1));
        h.record(MAX_HINTS*2, 1);
        assert!(h.contains(MAX_HINTS*2, 1));
    }
}
