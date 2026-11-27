#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in unchanged-page fast path for the pinned paired-wave runtime."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/xmem.rs")

REPLACEMENTS = (
    (
        "    let base = address as usize;\n    let mut physical = physical();\n    // Until the pages are mapped again:",
        """    let base = address as usize;
    let mut physical = physical();
    // Only a complete, exact match may skip the host mapping operations.
    // Keep the same remapping guard and the dirty notification used by
    // alias_in_runs: equal mappings do not imply equal contents.
    if skip_same() && !pages.is_null() && n != 0 && base % PAGE == 0
        && n.checked_mul(PAGE).and_then(|bytes| base.checked_add(bytes)).is_some()
    {
        // SAFETY: same caller contract as the normal mapping path.
        let requested = unsafe { std::slice::from_raw_parts(pages, n) };
        if requested.iter().enumerate().all(|(i, page)| {
            physical.pages.get(page).is_some_and(|want| {
                shown_slice(&physical, base + i * PAGE)
                    .is_some_and(|have| same_slice(&have, want))
            })
        }) {
            let _changing = victory_gpu::title_memory_remapping();
            drop(physical);
            victory_gpu::title_memory_written(base, n * PAGE, true);
            // Keep direct mappings out of the existing alias-only rate counters.
            static SKIPPED: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
            let count = SKIPPED.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
            if count.is_power_of_two() {
                tracing::info!(count, "unchanged physical mapping requests skipped");
            }
            return address;
        }
    }
    // Until the pages are mapped again:""",
    ),
    (
        "    let ok = if alias_runs() { alias_in_runs(&mut physical, to, from, len) } else { alias_pages(&mut physical, to, from, len) };",
        """    if skip_same() && from != 0 && len != 0 && len % PAGE == 0
        && from % PAGE == 0 && to % PAGE == 0
        && from.checked_add(len).is_some() && to.checked_add(len).is_some()
        && (0..len).step_by(PAGE).all(|k| {
            shown_slice(&physical, from + k).is_some_and(|want| {
                shown_slice(&physical, to + k)
                    .is_some_and(|have| same_slice(&have, &want))
            })
        })
    {
        drop(physical);
        victory_gpu::title_memory_written(to, len, true);
        alias_line([1, (len / PAGE) as u64, (len / PAGE) as u64, 0,
                    started.elapsed().as_micros() as u64]);
        return true;
    }
    let ok = if alias_runs() { alias_in_runs(&mut physical, to, from, len) } else { alias_pages(&mut physical, to, from, len) };""",
    ),
    (
        "fn alias_runs() -> bool {",
        """fn skip_same() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| std::env::var_os("VICTORY_MAP_SKIP_SAME").is_some_and(|v| v == "1"))
}

fn same_slice(a: &Slice, b: &Slice) -> bool {
    Arc::ptr_eq(&a.section, &b.section) && a.index == b.index
}

fn alias_runs() -> bool {""",
    ),
    (
        "        // The same page at a second address shows the same bytes.",
        """        // Repeating an identical physical mapping must preserve bytes.
        // Exercise with VICTORY_MAP_SKIP_SAME=1 and with it unset.
        unsafe { a.cast::<u8>().write(42); }
        assert_eq!(XMemMapPhysicalPages(a, 3, pages.as_ptr()), a);
        assert_eq!(unsafe { a.cast::<u8>().read() }, 42);

        // The same page at a second address shows the same bytes.""",
    ),
    (
        "        assert!(map_alias(b as u64, at(a, 2) as u64, PAGE as u64));",
        """        assert!(map_alias(b as u64, at(a, 2) as u64, PAGE as u64));
        assert!(map_alias(b as u64, at(a, 2) as u64, PAGE as u64));
        unsafe { at(a, 2).cast::<u8>().write(7); }
        assert_eq!(unsafe { b.cast::<u8>().read() }, 7);""",
    ),
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
        result = transform(path.read_text(encoding="utf-8"))
        path.write_text(result, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Mapping fast-path preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
