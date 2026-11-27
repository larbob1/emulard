#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in allocation-free storage page checks and single-run resolution."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/xmem.rs")
REPLACEMENTS = (
    ("/// Whether every page under `[offset, offset + len)` is known (a write that",
     "fn storage_page_lookup_on() -> bool {\n    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    *ON.get_or_init(|| std::env::var_os(\"VICTORY_STORAGE_PAGE_LOOKUP\").is_some_and(|v| v == \"1\"))\n}\n\n// Exactly the same page-range calculation as runs(), including empty\n// aligned ranges and zero-length unaligned ranges.\nfn storage_touched(pages: &[usize], offset: usize, len: usize) -> Option<&[usize]> {\n    let end = offset.checked_add(len)?;\n    pages.get(offset / PAGE..end.div_ceil(PAGE))\n}\n\nfn storage_known(pages: &[usize], offset: usize, len: usize) -> bool {\n    let Some(touched) = storage_touched(pages, offset, len) else { return false; };\n    let physical = physical();\n    touched.iter().all(|id| physical.pages.contains_key(id))\n}\n\nfn storage_single_run(pages: &[usize], offset: usize, len: usize) -> Option<(Slice, usize)> {\n    let touched = storage_touched(pages, offset, len)?;\n    let (first, rest) = touched.split_first()?;\n    let physical = physical();\n    let first = physical.pages.get(first)?;\n    for (k, id) in rest.iter().enumerate() {\n        let next = physical.pages.get(id)?;\n        if !Arc::ptr_eq(&first.section, &next.section)\n            || first.index.checked_add(k + 1) != Some(next.index)\n        {\n            return None;\n        }\n    }\n    Some((first.clone(), touched.len()))\n}\n\n/// Whether every page under `[offset, offset + len)` is known (a write that"),
    ("    runs(pages, offset, len).is_some()\n}",
     "    if storage_page_lookup_on() {\n        storage_known(pages, offset, len)\n    } else {\n        runs(pages, offset, len).is_some()\n    }\n}"),
    ("    let runs = runs(pages, offset, len)?;\n    let [(slice, n)] = runs.as_slice() else {\n        return None;\n    };\n    Some(PageWindow {",
     "    if storage_page_lookup_on() {\n        let (slice, n) = storage_single_run(pages, offset, len)?;\n        return Some(PageWindow {\n            view: View::map(&slice, n)?,\n            within: offset % PAGE,\n            len,\n        });\n    }\n    let runs = runs(pages, offset, len)?;\n    let [(slice, n)] = runs.as_slice() else {\n        return None;\n    };\n    Some(PageWindow {"),
    ("    fn physical_pages_map_alias_and_unmap() {",
     "    fn storage_page_lookup_matches_run_planner() {\n        let mut ids = [0usize; 4];\n        let mut n = ids.len();\n        assert_eq!(XMemAllocatePhysicalPages(0, &mut n, ids.as_mut_ptr()), 1);\n        assert_eq!(n, 4);\n        let mut other = [0usize; 1];\n        let mut one = 1;\n        assert_eq!(XMemAllocatePhysicalPages(0, &mut one, other.as_mut_ptr()), 1);\n        let lists = [\n            ids,\n            [ids[0], ids[0], ids[2], ids[3]],\n            [ids[2], ids[1], ids[0], ids[3]],\n            [ids[0], other[0], ids[2], ids[3]],\n            [ids[0], usize::MAX, ids[2], ids[3]],\n        ];\n        for pages in lists {\n            for offset in [0, 1, PAGE - 1, PAGE, 2 * PAGE + 7, 4 * PAGE, usize::MAX] {\n                for len in [0, 1, PAGE, PAGE + 3, 3 * PAGE, usize::MAX] {\n                    let reference = runs(&pages, offset, len);\n                    assert_eq!(storage_known(&pages, offset, len), reference.is_some());\n                    let expected = reference.as_deref().and_then(|r| {\n                        let [(slice, count)] = r else { return None; };\n                        Some((slice, *count))\n                    });\n                    let actual = storage_single_run(&pages, offset, len);\n                    match (actual, expected) {\n                        (None, None) => (),\n                        (Some((a, na)), Some((b, nb))) => {\n                            assert_eq!(na, nb);\n                            assert_eq!(a.index, b.index);\n                            assert!(Arc::ptr_eq(&a.section, &b.section));\n                        }\n                        _ => panic!(\"storage lookup mismatch\"),\n                    }\n                }\n            }\n        }\n        // Exercise the actual PageWindow path with the configured switch.\n        {\n            let mut window = page_window(&ids, PAGE - 2, 4).unwrap();\n            window.bytes().copy_from_slice(&[7, 8, 9, 10]);\n        }\n        let mut read = page_window(&ids, PAGE - 2, 4).unwrap();\n        assert_eq!(read.bytes(), &[7, 8, 9, 10]);\n        drop(read);\n        assert!(page_window(&[ids[0], ids[2]], 0, 2 * PAGE).is_none());\n        assert!(pages_known(&ids, 0, 4 * PAGE));\n        assert!(!pages_known(&[ids[0], usize::MAX], 0, 2 * PAGE));\n        assert_eq!(XMemFreePhysicalPages(n, ids.as_ptr()), 1);\n        assert_eq!(XMemFreePhysicalPages(one, other.as_ptr()), 1);\n        assert!(!storage_known(&ids, 0, PAGE));\n    }\n\n    #[test]\n    fn physical_pages_map_alias_and_unmap() {"),
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
        parser.exit(1, f"Storage page lookup preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
