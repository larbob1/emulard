#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only exact staging bounds preview; never modifies a checkout."""
import argparse
import difflib
import hashlib
from pathlib import Path

PATH = "crates/victory-gpu/src/texture.rs"
BEFORE = "fe0526831acf2b0f68caa4163fda83b251c22bb0"
AFTER = "30d690616b8e215e3019e2c41d12287e247f92ad"
ANCHORS = [
  [
    "fn staging_buffer(host: &crate::host::Host, total: u64) -> Option<(ID3D12Resource, *mut u8, u64)> {\n    let size = total.max(64 << 10).next_power_of_two();\n    if size > SPARE_MOST.1 || !staging_pool() {\n        // (Counted as made: the frame log's \"staging N made\" is then the\n        // buffers of a run without the pool too.)\n        SPARE_STATS[1].fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n        return host.upload_buffer(total).map(|(buffer, data)| (buffer, data, 0));\n    }\n    let spare = {\n        let mut all = SPARE.lock().unwrap_or_else(|e| e.into_inner());\n        let taken = all.0.get_mut(&size).and_then(Vec::pop);\n        if taken.is_some() {\n            all.1 -= size;\n        }\n        taken\n    };\n    if let Some(Spare(buffer, data)) = spare {\n        SPARE_STATS[0].fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n        // SAFETY: the buffer's own mapping, `size` bytes, which nothing\n        // else holds.\n        unsafe { std::ptr::write_bytes(data as *mut u8, 0, total as usize) };\n        return Some((buffer, data as *mut u8, size));\n    }\n    SPARE_STATS[1].fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n    host.upload_buffer(size).map(|(buffer, data)| (buffer, data, size))\n}",
    "// Validate immutable footprint metadata before any mapped slice is formed.\n// Keep the API's logical total distinct from the full padded CPU extent.\nfn staging_extent(\n    total: u64,\n    footprints: &[D3D12_PLACED_SUBRESOURCE_FOOTPRINT],\n    rows: &[u32],\n    active_rows: &[u64],\n    layout: &victory_formats::texture::Layout,\n    mips: u32,\n) -> Option<u64> {\n    let n = footprints.len();\n    // A 3D mip contains all its depth slices in one D3D subresource.\n    // Layout::linear reports depth in slices even for a volume.\n    let slices = if layout.desc.dimension == victory_formats::texture::Dimension::Tex3d { 1 } else { layout.slices as usize };\n    if total == 0 || total == u64::MAX || mips == 0\n        || layout.mips.len() != mips as usize\n        || (mips as usize).checked_mul(slices)? != n\n        || n == 0 || rows.len() != n || active_rows.len() != n\n    {\n        return None;\n    }\n    let mut full = 0u64;\n    for (i, footprint) in footprints.iter().enumerate() {\n        let f = footprint.Footprint;\n        let pitch = u64::from(f.RowPitch);\n        let active = active_rows[i];\n        let m = &layout.mips[i % mips as usize];\n        let layout_row = u64::from(m.width).checked_mul(u64::from(layout.desc.element_bytes))?;\n        if footprint.Offset % 512 != 0 || pitch % 256 != 0\n            || active == 0 || active > pitch || active != layout_row\n            || rows[i] == 0 || rows[i] != m.height || f.Depth == 0 || f.Depth != m.depth\n            || footprint.Offset < full\n        {\n            return None;\n        }\n        let count = u64::from(rows[i]).checked_mul(u64::from(f.Depth))?;\n        let end = footprint.Offset.checked_add(pitch.checked_mul(count - 1)?)?.checked_add(active)?;\n        full = footprint.Offset.checked_add(pitch.checked_mul(count)?)?;\n        if end > total || full > isize::MAX as u64 {\n            return None;\n        }\n    }\n    let required = total.max(full);\n    (required <= isize::MAX as u64).then_some(required)\n}\n\n// The mapped resource's declared width, not its physical heap granularity,\n// bounds the CPU slice. Pool keys must also agree with this actual width.\nfn staging_mapping_fits(buffer: &ID3D12Resource, data: *mut u8,\n                        required: u64, width: u64) -> bool {\n    !data.is_null() && required != 0 && required <= width\n        && width <= isize::MAX as u64\n        && unsafe { buffer.GetDesc().Width } == width\n}\n\nfn staging_buffer(host: &crate::host::Host, required: u64) -> Option<(ID3D12Resource, *mut u8, u64)> {\n    if required == 0 || required > isize::MAX as u64 { return None; }\n    let size = required.max(64 << 10).checked_next_power_of_two()?;\n    if size > SPARE_MOST.1 || !staging_pool() {\n        SPARE_STATS[1].fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n        let (buffer, data) = host.upload_buffer(required)?;\n        return staging_mapping_fits(&buffer, data, required, required)\n            .then_some((buffer, data, 0));\n    }\n    let spare = {\n        let mut all = SPARE.lock().unwrap_or_else(|e| e.into_inner());\n        let taken = all.0.get_mut(&size).and_then(Vec::pop);\n        if taken.is_some() { all.1 -= size; }\n        taken\n    };\n    if let Some(Spare(buffer, data)) = spare {\n        let data = data as *mut u8;\n        if !staging_mapping_fits(&buffer, data, required, size) { return None; }\n        SPARE_STATS[0].fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n        // SAFETY: uniquely held spare, verified mapped width and extent.\n        // Include last-row padding, not just the logical API total.\n        unsafe { std::ptr::write_bytes(data, 0, required as usize) };\n        return Some((buffer, data, size));\n    }\n    SPARE_STATS[1].fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n    // As before, new committed upload resources are initially zeroed.\n    let (buffer, data) = host.upload_buffer(size)?;\n    staging_mapping_fits(&buffer, data, required, size).then_some((buffer, data, size))\n}"
  ],
  [
    "    let mut rows = vec![0u32; count as usize];\n    let mut total = 0;",
    "    let mut rows = vec![0u32; count as usize];\n    let mut active_rows = vec![0u64; count as usize];\n    let mut total = 0;"
  ],
  [
    "            Some(rows.as_mut_ptr()),\n            None,\n            Some(&mut total),\n        );\n    }\n    let (buffer, data, pooled) = staging_buffer(host, total)?;",
    "            Some(rows.as_mut_ptr()),\n            Some(active_rows.as_mut_ptr()),\n            Some(&mut total),\n        );\n    }\n    let required = staging_extent(total, &footprints, &rows, &active_rows, &layout, u32::from(d.MipLevels))?;\n    let (buffer, data, pooled) = staging_buffer(host, required)?;"
  ],
  [
    "    /// Its bytes.\n    #[cfg(feature = \"diagnostics\")]\n    size: u64,",
    "    /// Full mapped CPU extent used by staging diagnostics.\n    #[cfg(feature = \"diagnostics\")]\n    size: u64,"
  ],
  [
    "        size: total,\n        data,\n        footprints,",
    "        size: required,\n        data,\n        footprints,"
  ]
]

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def transform(raw):
    raw = raw.replace(b"\r\n", b"\n")
    if b"\r" in raw or blob(raw) != BEFORE:
        raise ValueError("prepared staging source identity")
    text = raw.decode("utf-8")
    for old, new in ANCHORS:
        if text.count(old) != 1:
            raise ValueError("nonunique pinned anchor")
        text = text.replace(old, new, 1)
    result = text.encode("utf-8")
    if blob(result) != AFTER:
        raise ValueError("staging postimage identity")
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkout", type=Path)
    a = p.parse_args()
    raw = (a.checkout / PATH).read_bytes()
    candidate = transform(raw)
    print("".join(difflib.unified_diff(raw.replace(b"\r\n", b"\n").decode().splitlines(True),
        candidate.decode().splitlines(True), fromfile="a/" + PATH, tofile="b/" + PATH)), end="")

if __name__ == "__main__":
    main()
