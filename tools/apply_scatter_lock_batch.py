#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in bounded lock batching for changed scatter pages."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/xmem.rs")
REPLACEMENTS = (
    ("/// One page at each address; null `pages`, or a page number 0, unmaps",
     "fn scatter_batch_on() -> bool {\n    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    *ON.get_or_init(|| std::env::var_os(\"VICTORY_MAP_SCATTER_LOCK_BATCH\").is_some_and(|v| v == \"1\"))\n}\n\n// Bounded ordered prefix of changed, nonzero, aligned pages. Hold the\n// established lock order (physical then mapping) once for this prefix.\n// Keep the exact single-page host operations and stop at first refusal.\n// The caller handles clears, unchanged/invalid entries and unusual\n// addresses with the original scatter path.\nfn scatter_changed_prefix(addresses: *const *mut c_void, pages: *const usize, count: usize) -> (usize, bool) {\n    if count < 2 || pages.is_null() { return (0, true); }\n    let mut physical = physical();\n    let eligible = |physical: &Physical, index: usize| -> Option<(usize, Slice)> {\n        // SAFETY: caller has provided count entries, at most 64.\n        let (at, page) = unsafe { (*addresses.add(index) as usize, *pages.add(index)) };\n        if at == 0 || at % PAGE != 0 || at.checked_add(PAGE).is_none() || page == 0 {\n            return None;\n        }\n        let want = physical.pages.get(&page)?;\n        if shown_slice(physical, at).is_some_and(|have| same_slice(&have, want)) {\n            return None;\n        }\n        Some((at, want.clone()))\n    };\n    // Avoid taking the writer guard for a prefix that cannot start.\n    if eligible(&physical, 0).is_none() { return (0, true); }\n    let _changing = victory_gpu::title_memory_remapping();\n    let mut done = 0;\n    while done < count {\n        // Recheck after each mutation, including duplicate destinations.\n        let Some((at, want)) = eligible(&physical, done) else { break; };\n        if !unmap(&mut physical, at, PAGE) || !map(&mut physical, at, PAGE, want) {\n            scatter_batch_counts(done, true);\n            return (done, false);\n        }\n        done += 1;\n    }\n    scatter_batch_counts(done, false);\n    (done, true)\n}\n\nfn scatter_batch_counts(done: usize, failed: bool) {\n    use std::sync::atomic::{AtomicU64, Ordering};\n    static BATCHES: AtomicU64 = AtomicU64::new(0);\n    static PAGES: AtomicU64 = AtomicU64::new(0);\n    static FAILURES: AtomicU64 = AtomicU64::new(0);\n    PAGES.fetch_add(done as u64, Ordering::Relaxed);\n    if failed { FAILURES.fetch_add(1, Ordering::Relaxed); }\n    let batches = BATCHES.fetch_add(1, Ordering::Relaxed) + 1;\n    if batches.is_power_of_two() {\n        tracing::info!(batches, pages = PAGES.load(Ordering::Relaxed), failures = FAILURES.load(Ordering::Relaxed), \"scatter lock batch totals\");\n    }\n}\n\n/// One page at each address; null `pages`, or a page number 0, unmaps"),
    ("        // SAFETY: the title passes `n` addresses and, unless null, `n` pages.\n        let (address, page) = unsafe {",
     "        if scatter_batch_on() && !pages.is_null() && n - i >= 2 {\n            // SAFETY: both arrays have n entries and i < n.\n            let (done, ok) = scatter_changed_prefix(\n                unsafe { addresses.add(i) }, unsafe { pages.add(i) }, (n - i).min(64));\n            if !ok { return 0; }\n            if done != 0 { i += done; continue; }\n        }\n        // SAFETY: the title passes `n` addresses and, unless null, `n` pages.\n        let (address, page) = unsafe {"),
    ("        // One unchanged page followed by a contiguous changed run.",
     "        // A changed prefix before an invalid page must remain applied;\n        // the invalid destination and all later entries stay unchanged.\n        let prefix_failure = [pages[2], usize::MAX, pages[0]];\n        assert_eq!(XMemMapPhysicalPagesScatter(consecutive.as_ptr(), 3, prefix_failure.as_ptr()), 0);\n        unsafe {\n            assert_eq!(a.cast::<u8>().read(), 44);\n            assert_eq!(at(a, 1).cast::<u8>().read(), 22);\n            assert_eq!(at(a, 2).cast::<u8>().read(), 44);\n        }\n        assert_eq!(XMemMapPhysicalPages(a, 3, pages.as_ptr()), a);\n        // Two changed requests for the same destination execute in order.\n        let ordered_duplicate = [a, a];\n        let ordered_pages = [pages[1], pages[2]];\n        assert_eq!(XMemMapPhysicalPagesScatter(ordered_duplicate.as_ptr(), 2, ordered_pages.as_ptr()), 1);\n        assert_eq!(unsafe { a.cast::<u8>().read() }, 44);\n        assert_eq!(XMemMapPhysicalPages(a, 3, pages.as_ptr()), a);\n        // One unchanged page followed by a contiguous changed run."),
)

def transform(source):
    for old, new in REPLACEMENTS:
        if source.count(old) != 1:
            raise ValueError("Expected exactly one pinned source anchor: " + old[:80])
        source = source.replace(old, new, 1)
    return source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    path = args.checkout / PATH
    try:
        path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Scatter lock batch preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
