#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only window geometry regressions on exact prepared pinned source."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-gpu/src/shadow.rs")
OLD = """    /// A window holds its ask and is cut on the grid; on the default grid
    /// it is the window there always was."""
NEW = """    // Deterministic examples, not title traces or resident-memory estimates.
    // Exact named ranges must stay stable within each fixed grid.
    fn named(asks: &[(u64, u64)], g: u64) -> Vec<(u64, u64)> {
        let mut keys: Vec<_> = asks.iter().map(|&(a, e)| window_of(a, e, g)).collect();
        keys.sort_unstable();
        keys.dedup();
        keys
    }

    #[test]
    fn half_grid_reduces_clustered_named_window_capacity() {
        let base = 16 * WINDOW;
        let asks = [(base + 4096, base + 8192),
                    (base + WINDOW + 4096, base + WINDOW + 8192)];
        let full = named(&asks, grid(Some(4096)));
        let half = named(&asks, grid(Some(2048)));
        assert_eq!(full.len(), 2);
        assert_eq!(half.len(), 2);
        assert_eq!(full.iter().map(|k| k.1).sum::<u64>(), 2 * WINDOW);
        assert_eq!(half.iter().map(|k| k.1).sum::<u64>(), WINDOW);
        assert_eq!(cover(half.into_iter()), WINDOW);
    }

    #[test]
    fn half_grid_can_increase_named_overlap_for_crossing_asks() {
        let base = 16 * WINDOW;
        let middle = base + WINDOW / 2;
        let asks = [(base + 4096, base + 8192),
                    (middle - 4096, middle + 4096)];
        let full = named(&asks, WINDOW);
        let half = named(&asks, grid(Some(2048)));
        assert_eq!(full, vec![(base, WINDOW)]);
        assert_eq!(half, vec![(base, WINDOW / 2), (base, WINDOW)]);
        assert_eq!(half.iter().map(|k| k.1).sum::<u64>(), WINDOW + WINDOW / 2);
        assert_eq!(cover(half.iter().copied()), WINDOW);
        // Transient find_any may take the larger existing complete window;
        // descriptor find uses the named key instead.
        assert_eq!(holder(half.into_iter(), asks[0].0, asks[0].1), Some((base, WINDOW)));
    }

    #[test]
    fn sized_and_unsized_window_keys_remain_distinct_when_needed() {
        let base = 16 * WINDOW;
        let ask = base + WINDOW / 2 + 4096;
        let sized = window_of(ask, ask + 4096, grid(Some(2048)));
        // Existing loose() explicitly passes WINDOW for a lengthless ask.
        let unsized = window_of(ask, ask + 1, WINDOW);
        assert_eq!(sized, (base + WINDOW / 2, WINDOW / 2));
        assert_eq!(unsized, (base, WINDOW));
        assert_ne!(sized, unsized);
        assert_eq!(cover([unsized, sized].into_iter()), WINDOW);
    }

    /// A window holds its ask and is cut on the grid; on the default grid
    /// it is the window there always was."""

def transform(text):
    if text.count(OLD) != 1 or NEW in text:
        raise ValueError("missing, duplicate or applied window test anchor")
    return text.replace(OLD, NEW, 1)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    path = args.prepared / PATH
    try:
        path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")
    except (OSError, ValueError) as e:
        parser.exit(1, f"Window test preparation failed: {e}\n")

if __name__ == "__main__":
    main()
