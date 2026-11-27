#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check host unmap failures and preserve live view bookkeeping."""
import argparse
from pathlib import Path

PATCHES = {
    "crates/victory-hle/src/modules/xmem.rs": (
        ("    unmap(&mut physical, base, n * PAGE);\n    if pages.is_null()",
         "    if !unmap(&mut physical, base, n * PAGE) {\n        return std::ptr::null_mut();\n    }\n    if pages.is_null()"),
        ("            unmap(physical, at, bytes);\n            for k in i..end {",
         "            if !unmap(physical, at, bytes) {\n                diff_counts(saved, mapped, 0);\n                return (false, unchanged, mapped);\n            }\n            for k in i..end {"),
        ("        unmap(physical, to, len);\n        return true;",
         "        return unmap(physical, to, len);"),
        ("            unmap(physical, at, bytes);\n            if !map_run",
         "            if !unmap(physical, at, bytes) {\n                return false;\n            }\n            if !map_run"),
        ("        unmap(physical, to + wanted.len() * PAGE, len - wanted.len() * PAGE);",
         "        let _ = unmap(physical, to + wanted.len() * PAGE, len - wanted.len() * PAGE);"),
        ("    unmap(physical, to, len);\n    for k in",
         "    if !unmap(physical, to, len) {\n        return false;\n    }\n    for k in"),
        ("fn unmap(physical: &mut Physical, base: usize, len: usize) {",
         "fn unmap(physical: &mut Physical, base: usize, len: usize) -> bool {\n    unmap_with(physical, base, len, |at| {\n        // SAFETY: a tracked host view, protected by the remapping guard.\n        unsafe {\n            UnmapViewOfFile2(\n                GetCurrentProcess(),\n                MEMORY_MAPPED_VIEW_ADDRESS { Value: at as *mut c_void },\n                MEM_PRESERVE_PLACEHOLDER,\n            ) != 0\n        }\n    })\n}\n\n// The host operation is injectable for a deterministic failure fixture.\n// Previous successfully removed views are not rolled back; the table must\n// describe what actually remains mapped, and failure must reach the caller.\nfn unmap_with(\n    physical: &mut Physical, base: usize, len: usize,\n    mut host_unmap: impl FnMut(usize) -> bool,\n) -> bool {"),
        ("    if len == 0 {\n        return;\n    }\n    let end = base + len;\n    // Views do not overlap:",
         "    if len == 0 {\n        return true;\n    }\n    let Some(end) = base.checked_add(len) else { return false; };\n    // Views do not overlap:"),
        ("        let Some((size, slice)) = physical.views.remove(&at) else {\n            continue;\n        };\n        for k in 0..size.div_ceil(PAGE) {\n            let key = slice.key(k);\n            if let Some(addresses) = physical.shown.get_mut(&key) {\n                addresses.retain(|&a| a != at + k * PAGE);\n                if addresses.is_empty() {\n                    physical.shown.remove(&key);\n                }\n            }\n        }\n        use victory_gpu::framelog::{T, add};\n        let started = std::time::Instant::now();\n        victory_gpu::title_memory_remapped(at, size);",
         "        let Some((size, slice)) = physical.views.get(&at).cloned() else {\n            continue;\n        };\n        use victory_gpu::framelog::{T, add};\n        let started = std::time::Instant::now();\n        // Open only guards installed by the renderer before forgetting their\n        // records. If opening fails, do not attempt to remove this view.\n        if !victory_gpu::title_memory_prepare_unmap(at, size) {\n            return false;\n        }\n        victory_gpu::title_memory_remapped(at, size);"),
        ("        // SAFETY: a view we mapped; it becomes a placeholder again.\n        let unmapped = unsafe {\n            UnmapViewOfFile2(\n                GetCurrentProcess(),\n                MEMORY_MAPPED_VIEW_ADDRESS {\n                    Value: at as *mut c_void,\n                },\n                MEM_PRESERVE_PLACEHOLDER,\n            )\n        } != 0;\n        if unmapped && size == PAGE",
         "        let unmapped = host_unmap(at);\n        if !unmapped {\n            // The old view remains live. Keep the HLE index and restore the\n            // GPU-side view record invalidated before the host operation.\n            victory_gpu::title_memory_view(at, size, slice.section.0 as usize, (slice.index * PAGE) as u64);\n            add(T::RemapUnmapUs, noted.elapsed().as_micros() as u64);\n            tracing::warn!(\"host unmap failed; retaining existing physical view\");\n            return false;\n        }\n        physical.views.remove(&at);\n        for k in 0..size.div_ceil(PAGE) {\n            let key = slice.key(k);\n            if let Some(addresses) = physical.shown.get_mut(&key) {\n                addresses.retain(|&a| a != at + k * PAGE);\n                if addresses.is_empty() {\n                    physical.shown.remove(&key);\n                }\n            }\n        }\n        if size == PAGE"),
        ("        if at < base {\n            map(physical, at, base - at, slice.clone());\n        }\n        if at + size > end {\n            let index = slice.index + (end - at) / PAGE;\n            map(physical, end, at + size - end, Slice { index, ..slice });\n        }\n    }\n}\n\n/// The oldest layout",
         "        let mut restored = true;\n        if at < base {\n            restored &= map(physical, at, base - at, slice.clone());\n        }\n        if at + size > end {\n            let index = slice.index + (end - at) / PAGE;\n            restored &= map(physical, end, at + size - end, Slice { index, ..slice });\n        }\n        if !restored {\n            tracing::warn!(\"host unmap succeeded but a neighboring view could not be restored\");\n            return false;\n        }\n    }\n    true\n}\n\n/// The oldest layout"),
        ("        // Invalid requests on the diff path must not destroy valid mappings.",
         "        // Inject a failed host unmap without removing the actual view.\n        {\n            let mut physical = physical();\n            let _changing = victory_gpu::title_memory_remapping();\n            let before = shown_slice(&physical, a as usize).unwrap();\n            assert!(!unmap_with(&mut physical, a as usize, PAGE, |_| false));\n            assert!(same_slice(&before, &shown_slice(&physical, a as usize).unwrap()));\n            assert_eq!(unsafe { a.cast::<u8>().read() }, 11);\n        }\n\n        // Invalid requests on the diff path must not destroy valid mappings."),
    ),
    "crates/victory-gpu/src/watch.rs": (
        ("pub fn title_memory_remapped(at: usize, len: usize) {",
         "/// Before a host unmap that might fail, restore renderer-guarded blocks\n/// to their normal writable protection while the mapping guard is held.\n/// Leave the failed block tracked if the host refuses the protection change.\npub fn title_memory_prepare_unmap(at: usize, len: usize) -> bool {\n    use windows_sys::Win32::System::Memory::{PAGE_READWRITE, VirtualProtect};\n    let mut g = guards();\n    let blocks: Vec<usize> = g.protected.range(at / BLOCK..at.saturating_add(len).div_ceil(BLOCK)).copied().collect();\n    for block in blocks {\n        let mut old = 0;\n        // SAFETY: a block made read-only by the renderer.\n        if unsafe { VirtualProtect((block * BLOCK) as *const _, BLOCK, PAGE_READWRITE, &mut old) } == 0 {\n            return false;\n        }\n        g.protected.remove(&block);\n        g.clean.remove(&block);\n    }\n    true\n}\n\npub fn title_memory_remapped(at: usize, len: usize) {"),
    ),
    "crates/victory-gpu/src/lib.rs": (
        ("    title_memory_reading, title_memory_remapped, title_memory_remapping, title_memory_written,",
         "    title_memory_prepare_unmap, title_memory_reading, title_memory_remapped, title_memory_remapping, title_memory_written,"),
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
        parser.exit(1, f"Checked unmap preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
