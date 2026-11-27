#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Preflight all direct physical mapping requests before modifying views."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/xmem.rs")
REPLACEMENTS = (
    ("    if !unmap(&mut physical, base, n * PAGE) {\n        return std::ptr::null_mut();\n    }\n    if pages.is_null() {\n        return address;\n    }\n    // SAFETY: the title passes `n` page numbers.\n    let pages = unsafe { std::slice::from_raw_parts(pages, n) };\n    let mut i = 0;\n    while i < n {\n        let Some(first) = physical.pages.get(&pages[i]).cloned() else {\n            tracing::warn!(page = pages[i], \"XMemMapPhysicalPages: unknown page\");\n            return std::ptr::null_mut();\n        };\n        // One view per run of consecutive slices of one section.\n        let run = 1 + pages[i + 1..]\n            .iter()\n            .zip(1..)\n            .take_while(|&(page, k)| {\n                physical.pages.get(page).is_some_and(|s| {\n                    Arc::ptr_eq(&s.section, &first.section) && s.index == first.index + k\n                })\n            })\n            .count();\n        // A range previously split into several placeholders cannot be\n        // replaced by one section view on Windows until coalesced. First\n        // retain the original fast path for a single placeholder; if it\n        // fails, use the established coalesce-or-page mapping helper.\n        if !map(&mut physical, base + i * PAGE, run * PAGE, first.clone())\n            && (run == 1 || !map_run(&mut physical, base + i * PAGE, run, &first))\n        {\n            return std::ptr::null_mut();\n        }\n        i += run;\n    }",
     "    // Resolve every page before removing any destination view. Plan the\n    // same consecutive section runs as before in one pass. In particular,\n    // a bad page at the end of a request must not destroy earlier views.\n    if pages.is_null() {\n        return if unmap(&mut physical, base, n * PAGE) { address } else { std::ptr::null_mut() };\n    }\n    // SAFETY: the title passes `n` page numbers.\n    let pages = unsafe { std::slice::from_raw_parts(pages, n) };\n    let Some(plan) = physical_map_plan(&physical, pages) else {\n        tracing::warn!(\"XMemMapPhysicalPages: unknown page; destination unchanged\");\n        return std::ptr::null_mut();\n    };\n    if !unmap(&mut physical, base, n * PAGE) {\n        return std::ptr::null_mut();\n    }\n    let mut i = 0;\n    for (first, run) in plan {\n        // Preserve the existing coalesce-or-page fallback.\n        if !map(&mut physical, base + i * PAGE, run * PAGE, first.clone())\n            && (run == 1 || !map_run(&mut physical, base + i * PAGE, run, &first))\n        {\n            return std::ptr::null_mut();\n        }\n        i += run;\n    }"),
    ("/// One page at each address; null `pages`, or a page number 0, unmaps",
     "// Called under the existing physical and mapping locks. The plan keeps\n// backing sections alive and stores one entry per contiguous run.\nfn physical_map_plan(physical: &Physical, pages: &[usize]) -> Option<Vec<(Slice, usize)>> {\n    let mut plan: Vec<(Slice, usize)> = Vec::new();\n    for id in pages {\n        let slice = physical.pages.get(id)?;\n        if let Some((first, count)) = plan.last_mut()\n            && Arc::ptr_eq(&first.section, &slice.section)\n            && first.index.checked_add(*count) == Some(slice.index)\n        {\n            *count += 1;\n        } else {\n            plan.push((slice.clone(), 1));\n        }\n    }\n    Some(plan)\n}\n\n/// One page at each address; null `pages`, or a page number 0, unmaps"),
    ("        // Invalid requests on the diff path must not destroy valid mappings.\n        if diff_mapping() {\n            let invalid = [pages[0], usize::MAX, pages[2]];\n            assert!(XMemMapPhysicalPages(a, 3, invalid.as_ptr()).is_null());\n            assert_eq!(unsafe { at(a, 1).cast::<u8>().read() }, 22);\n            // b is reserved but not mapped at this point.",
     "        // Invalid physical requests must preserve the destination in all\n        // modes, including an invalid final ID after a valid changed run.\n        let invalid = [pages[1], pages[2], usize::MAX];\n        assert!(XMemMapPhysicalPages(a, 3, invalid.as_ptr()).is_null());\n        unsafe {\n            assert_eq!(a.cast::<u8>().read(), 11);\n            assert_eq!(at(a, 1).cast::<u8>().read(), 22);\n            assert_eq!(at(a, 2).cast::<u8>().read(), 44);\n        }\n        if diff_mapping() {\n            // b is reserved but not mapped at this point."),
    ("assert_eq!(at(b, k).cast::<u8>().add(64).read(), value, \"page {k}\");",
     "assert_eq!(at(b, k).cast::<u8>().add(64).read(), value, \"alias-check-{value} page {k}\");"),
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
        parser.exit(1, f"Mapping preflight preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
