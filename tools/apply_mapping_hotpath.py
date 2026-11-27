#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in mapping run and texture residency estimate candidates."""
import argparse
from pathlib import Path

PATCHES = {
    "crates/victory-hle/src/modules/xmem.rs": (
        ("// The caller holds both mapping locks. Split into contiguous unchanged\n// and changed spans. Only changed spans reach host map/unmap. Preserve\n// original page-by-page host mapping for changed spans to avoid relying\n// on Wine placeholder coalescing.",
         "fn diff_runs_on() -> bool {\n    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    *ON.get_or_init(|| std::env::var_os(\"VICTORY_MAP_DIFF_RUNS\").is_some_and(|v| v == \"1\"))\n}\n\n// The caller holds both mapping locks. Only changed spans reach host\n// map/unmap. With the independent opt-in switch, contiguous backing\n// slices inside a changed span can use the existing run mapper."),
        ("            for k in i..end {\n                if !map(physical, base + k * PAGE, PAGE, wanted[k].clone()) {\n                    diff_counts(saved, mapped, 0);\n                    return (false, unchanged, mapped);\n                }\n                mapped += 1;\n            }",
         "            let mut k = i;\n            while k < end {\n                let mut next = k + 1;\n                if diff_runs_on() {\n                    while next < end && follows(&wanted[next - 1], &wanted[next]) {\n                        next += 1;\n                    }\n                }\n                let count = next - k;\n                let address = base + k * PAGE;\n                let ok = if count > 1 {\n                    map_run(physical, address, count, &wanted[k])\n                } else {\n                    map(physical, address, PAGE, wanted[k].clone())\n                };\n                if !ok {\n                    // Count only completed runs; a failed host run may\n                    // have partly succeeded, as with the prior mapper.\n                    diff_counts(saved, mapped, 0);\n                    return (false, unchanged, mapped);\n                }\n                if count > 1 {\n                    diff_run_counts(count);\n                }\n                mapped += count;\n                k = next;\n            }"),
        ("// Cumulative counters; log only occasionally so measurement does not",
         "// Counts completed logical requests, not actual host syscalls.\nfn diff_run_counts(pages: usize) {\n    use std::sync::atomic::AtomicU64;\n    static RUNS: AtomicU64 = AtomicU64::new(0);\n    static PAGES: AtomicU64 = AtomicU64::new(0);\n    PAGES.fetch_add(pages as u64, Ordering::Relaxed);\n    let runs = RUNS.fetch_add(1, Ordering::Relaxed) + 1;\n    if runs.is_power_of_two() {\n        tracing::info!(runs, pages = PAGES.load(Ordering::Relaxed), \"mapping diff run totals\");\n    }\n}\n\n// Cumulative counters; log only occasionally so measurement does not"),
        ("        // Inject a failed host unmap without removing the actual view.",
         "        // One unchanged page followed by a contiguous changed run.\n        // Both switch modes must preserve the exact alias bytes.\n        let shifted = [pages[0], pages[0], pages[1]];\n        assert_eq!(XMemMapPhysicalPages(a, 3, shifted.as_ptr()), a);\n        unsafe {\n            assert_eq!(a.cast::<u8>().read(), 11);\n            assert_eq!(at(a, 1).cast::<u8>().read(), 11);\n            assert_eq!(at(a, 2).cast::<u8>().read(), 22);\n        }\n        assert_eq!(XMemMapPhysicalPages(a, 3, pages.as_ptr()), a);\n        assert_eq!(unsafe { at(a, 1).cast::<u8>().read() }, 22);\n        assert_eq!(unsafe { at(a, 2).cast::<u8>().read() }, 44);\n\n        // Inject a failed host unmap without removing the actual view."),
    ),
    "crates/victory-gpu/src/inplace.rs": (
        ("/// Whether `[at, at + len)` is private memory, all committed and",
         "// A coverage-only walk: unlike cover_in it does not care whether\n// adjacent views belong to the same physical section. Iterate once\n// over ordered view starts rather than doing a tree search per view.\n// Reject arithmetic overflow, holes, zero-length and overlapping entries.\nfn fully_covered_in(table: &BTreeMap<usize, (usize, usize, u64)>, at: usize, len: usize) -> bool {\n    let Some(end) = at.checked_add(len) else { return false; };\n    if len == 0 { return false; }\n    let Some((&base, &(bytes, _, _))) = table.range(..=at).next_back() else { return false; };\n    let Some(mut reached) = base.checked_add(bytes) else { return false; };\n    if reached <= at { return false; }\n    if reached >= end { return true; }\n    for (&start, &(bytes, _, _)) in table.range((std::ops::Bound::Excluded(base), std::ops::Bound::Unbounded)) {\n        if start != reached || bytes == 0 { return false; }\n        let Some(next) = start.checked_add(bytes) else { return false; };\n        reached = next;\n        if reached >= end { return true; }\n    }\n    false\n}\n\n// Only an estimate of mapped bytes, not proof of readable host memory.\n// The caller holds the established mapping read guard.\npub(crate) fn fully_covered_for_estimate(at: usize, len: usize, _reading: &crate::watch::Reading) -> bool {\n    fully_covered_in(&views().views, at, len)\n}\n\n#[cfg(test)]\nmod perf_hotpath_coverage_tests {\n    use super::*;\n    #[test]\n    fn handles_contiguous_scattered_holes_and_boundaries() {\n        let t = BTreeMap::from([(100, (20, 1, 0)), (120, (10, 2, 8)), (140, (10, 1, 40))]);\n        assert!(fully_covered_in(&t, 105, 25));\n        assert!(fully_covered_in(&t, 120, 10));\n        assert!(!fully_covered_in(&t, 105, 26));\n        assert!(!fully_covered_in(&t, 130, 1));\n        assert!(!fully_covered_in(&t, 99, 1));\n        assert!(!fully_covered_in(&t, 100, 0));\n        assert!(!fully_covered_in(&t, usize::MAX, 2));\n        assert!(!fully_covered_in(&BTreeMap::new(), 100, 1));\n    }\n    #[test]\n    fn agrees_with_existing_cover_for_valid_view_tables() {\n        let t = BTreeMap::from([(100, (20, 1, 0)), (120, (10, 2, 8)), (140, (10, 1, 40))]);\n        for at in 90..160 {\n            for len in 1..80 {\n                assert_eq!(fully_covered_in(&t, at, len),\n                    matches!(cover_in(&t, at, len), Cover::Run(..) | Cover::Scattered));\n            }\n        }\n    }\n}\n\n/// Whether `[at, at + len)` is private memory, all committed and"),
    ),
    "crates/victory-gpu/src/texture.rs": (
        ("    let end = start.saturating_add(len);\n    if !committed(at, 1) && !committed((end - 1) as *const u8, 1) {",
         "    let end = start.saturating_add(len);\n    // This is only a residency estimate. Do not change committed() or\n    // any direct title-memory dereference safety checks.\n    static VIEW_ESTIMATE: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    if *VIEW_ESTIMATE.get_or_init(|| std::env::var_os(\"VICTORY_TEXTURE_VIEW_ESTIMATE\").is_some_and(|v| v == \"1\"))\n        && let Some(reading) = crate::watch::title_memory_reading_now()\n        && crate::inplace::fully_covered_for_estimate(start, len, &reading)\n    {\n        use std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n        static HITS: AtomicU64 = AtomicU64::new(0);\n        let hits = HITS.fetch_add(1, Relaxed) + 1;\n        if hits.is_power_of_two() {\n            tracing::info!(hits, \"texture view estimate hits\");\n        }\n        return len as u64;\n    }\n    if !committed(at, 1) && !committed((end - 1) as *const u8, 1) {"),
    ),
}

def transform(source, replacements):
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError("Expected exactly one pinned source anchor: " + old[:80])
        source = source.replace(old, new, 1)
    return source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    try:
        changes = {}
        for relative, replacements in PATCHES.items():
            path = args.checkout / relative
            changes[path] = transform(path.read_text(encoding="utf-8"), replacements)
        for path, content in changes.items():
            path.write_text(content, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Mapping hotpath preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
