#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Move raw-address descriptor runs into their owning host heaps."""
import argparse
from pathlib import Path
import subprocess
import sys
from apply_memory_patch import blob_hash, patch_source as memory_patch
from apply_fault_bitmap import SPECS as FEEDBACK_SPECS, transform as feedback_patch

SPECS = [["crates/victory-gpu/src/memory.rs","c25636783511fdfbf9692fdd36ef150f69ea666e",[["use std::collections::HashMap;\n",""],["    /// Per host view heap (by address): the first slot of its run, and how\n    /// many copies have their view there.\n    heaps: HashMap<usize, (u32, u32)>,\n",""],["            heaps: HashMap::new(),\n",""],["    let key = std::ptr::from_ref(heap) as usize;\n    let (base, made) = match m.heaps.get(&key) {\n        Some(&run) => run,\n        None => {\n            // Held for the heap's life: not given back with a list's slots.\n            let base = heap.dynamic(COPIES + 1)?;\n            heap.null_raw_uav_at(base);\n            (base, 0)\n        }\n    };\n    for (n, shadow) in m.copies.iter().enumerate().skip(made as usize) {\n        let (_, len) = shadow.span();\n        heap.raw_uav_at(base + 1 + n as u32, &shadow.buffer, 0, len);\n    }\n    m.heaps.insert(key, (base, m.copies.len() as u32));","    // The descriptor run belongs to the heap object, not its address.\n    // A newly allocated heap must never inherit another heap's slots.\n    let base = heap.raw_memory_slots(&m.copies, COPIES)?;"],["const PAGE: u64 = 1 << 16;","const PAGE: u64 = 1 << 16;\n\n/// Raw shader addresses use a 32-bit byte offset within a copy.\n/// Require the whole page to fit, not just its first byte.\nfn checked_page_offset(first: u64, len: u64, page: u64) -> Option<u32> {\n    let offset = page.checked_sub(first)?;\n    let end = offset.checked_add(PAGE)?;\n    if offset % 4 != 0 || end > len || end > (1u64 << 32) {\n        return None;\n    }\n    u32::try_from(offset).ok()\n}\n\n#[cfg(test)]\nmod directory_range_tests {\n    use super::{checked_page_offset, PAGE};\n\n    #[test]\n    fn a_complete_page_must_fit_the_shader_byte_offset() {\n        let first = 1u64 << 36;\n        let len = (1u64 << 32) + PAGE;\n        assert_eq!(checked_page_offset(first, len, first), Some(0));\n        assert_eq!(checked_page_offset(first, len, first + (1u64 << 32) - PAGE),\n                   Some((u32::MAX as u64 + 1 - PAGE) as u32));\n        assert_eq!(checked_page_offset(first, len, first + (1u64 << 32)), None);\n        assert_eq!(checked_page_offset(first, PAGE - 1, first), None);\n        assert_eq!(checked_page_offset(first, len, first - PAGE), None);\n        assert_eq!(checked_page_offset(first + 1, len, first + PAGE), None);\n    }\n}"],["        let whole = |s: &Arc<Shadow>| s.offset_in(start).is_some_and(|_| s.left(start) >= PAGE);","        let whole = |s: &Arc<Shadow>| {\n            let (first, len) = s.span();\n            checked_page_offset(first, len, start).is_some()\n        };"],["                let mut at = first.next_multiple_of(PAGE);\n                while at + PAGE <= first + len && at / PAGE < u64::from(MEMORY_PAGES) - 1 {","                // Do not publish pages merely because a shadow covers them.\n                let whole_readable = len <= CELL\n                    && crate::texture::committed(first as *const u8, len as usize);\n                let mut at = first.saturating_add(PAGE - 1) & !(PAGE - 1);\n                while whole_readable && at / PAGE < u64::from(MEMORY_PAGES) - 1 {\n                    let Some(offset) = checked_page_offset(first, len, at) else { break };"],["other.add(1).write_volatile((at - first) as u32);","other.add(1).write_volatile(offset);"],["        let offset = shadow.offset_in(start).unwrap_or(0);","        let (first, len) = shadow.span();\n        let Some(offset) = checked_page_offset(first, len, start) else { return };"],["entry.add(1).write_volatile(offset as u32);","entry.add(1).write_volatile(offset);"],["                    first = format_args!(\"{:#x}\", u64::from(pages[0]) * PAGE),\n",""],["        self.map((address & !(CELL - 1)) + CELL);","        if let Some(next) = (address & !(CELL - 1)).checked_add(CELL) {\n            self.map(next);\n        }"],["        let flags = unsafe { shadow.buffer.GetDesc() }.Flags;\n        if flags.0 & D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS.0 == 0 {\n            return;\n        }","        let desc = unsafe { shadow.buffer.GetDesc() };\n        let (first, len) = shadow.span();\n        // Directory offsets are u32, and the raw view must cover the\n        // same bytes as root views, including an in-place view's bias.\n        let bias = shadow.offset(first);\n        if desc.Flags.0 & D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS.0 == 0\n            || bias % 4 != 0 || len % 4 != 0 || len > u64::from(u32::MAX) + 1\n            || bias.checked_add(len).is_none_or(|end| end > desc.Width)\n        {\n            self.refused.insert(page);\n            return;\n        }"]]],["crates/victory-gpu/src/descriptor/host.rs","e91db795b279fbe02a72f3c87646b53a1a12d7a4",[["    pub(crate) heap: ID3D12DescriptorHeap,\n","    pub(crate) heap: ID3D12DescriptorHeap,\n    /// Raw-address descriptor slots owned by this heap.\n    raw_memory: Mutex<Option<(u32, usize)>>,\n"],["        let h = HostHeap {\n            heap,","        let h = HostHeap {\n            heap,\n            raw_memory: Mutex::default(),"],["    pub(crate) fn dynamic(&self, n: u32) -> Option<u32> {","    /// Reserve a raw-memory descriptor run for this heap's own lifetime.\n    /// Initialize every slot before publishing it: a directory entry\n    /// created after this list was recorded can otherwise name an\n    /// uninitialized descriptor on an older heap.\n    pub(crate) fn raw_memory_slots(\n        &self, copies: &[std::sync::Arc<crate::shadow::Shadow>], capacity: u32,\n    ) -> Option<u32> {\n        if copies.len() > capacity as usize {\n            return None;\n        }\n        let mut run = self.raw_memory.lock().unwrap_or_else(|e| e.into_inner());\n        let (base, made) = match *run {\n            Some((base, made)) => (base, made),\n            None => {\n                let base = self.dynamic(capacity.checked_add(1)?)?;\n                for slot in 0..=capacity {\n                    self.null_raw_uav_at(base + slot);\n                }\n                (base, 0)\n            }\n        };\n        for (n, shadow) in copies.iter().enumerate().skip(made) {\n            let (start, len) = shadow.span();\n            self.raw_uav_at(base + 1 + n as u32, &shadow.buffer, shadow.offset(start), len);\n        }\n        *run = Some((base, copies.len()));\n        Some(base)\n    }\n\n    pub(crate) fn dynamic(&self, n: u32) -> Option<u32> {"]]]]

def normalize(data):
    return data.replace(b"\r\n", b"\n")

def transform(data, edits):
    source = normalize(data).decode("utf-8")
    for before, after in edits:
        if source.count(before) != 1:
            raise ValueError("Descriptor lifetime anchor differs.")
        source = source.replace(before, after)
    result = source.encode("utf-8")
    return result.replace(b"\n", b"\r\n") if b"\r\n" in data else result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--lighting-memory", action="store_true")
    args = parser.parse_args()
    root = args.checkout.resolve()
    try:
        if not (root / ".git").exists():
            raise ValueError("Separate checkout required.")
        pending = {}
        for path, expected, edits in SPECS:
            target = root / path
            if target.resolve() != target or not target.is_file():
                raise ValueError("Invalid source path.")
            original = subprocess.check_output(["git", "show", "HEAD:" + path], cwd=root)
            if blob_hash(normalize(original)) != expected:
                raise ValueError("Pinned source differs.")
            predecessor = original
            if path == SPECS[0][0]:
                predecessor = memory_patch(path, original)
                if args.lighting_memory:
                    feedback_edits = next(e for p, _, e in FEEDBACK_SPECS if p == path)
                    predecessor = feedback_patch(predecessor, feedback_edits)
            current = target.read_bytes()
            if normalize(current) != normalize(predecessor):
                raise ValueError("Unexpected predecessor source.")
            pending[target] = transform(current, edits)
        if args.apply:
            for target, data in pending.items():
                target.write_bytes(data)
        print("Descriptor lifetime source checks passed.")
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Descriptor lifetime preparation failed.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
