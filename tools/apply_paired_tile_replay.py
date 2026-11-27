#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Port existing tile mapping replay fixture to the paired-wave runtime."""
import argparse
from pathlib import Path

QUEUE = Path("crates/victory-gpu/src/queue.rs")
XMEM = Path("crates/victory-hle/src/modules/xmem.rs")
FIXTURE = Path("crates/victory-hle/src/modules/xmem_tile_replay.rs")
MODEL = FIXTURE.with_name("xmem_software_pages.rs")
REPLACEMENTS = (
    ("/// Bytes per mapped page.\nconst PAGE: u64 = 64 << 10;\n\n/// `CopyPageMappingsBatchX(count, batches, pool, pool pages, flags)`: maps\n/// pages of a pool (memory the title mapped physical pages into) at the\n/// batches' addresses. The title streams textures into pool pages",
     "/// Bytes per mapped page.\nconst PAGE: u64 = 64 << 10;\n\n/// Records mapping requests without reading title memory or changing the\n/// order in which the live mapper sees them.\n#[cfg(feature = \"diagnostics\")]\nfn trace_page_ranges(destination: u64, pool: u64, pool_pages: u32, ranges: &[PageRange]) {\n    use std::io::{BufWriter, Write};\n    use std::sync::{Mutex, OnceLock};\n\n    struct Trace {\n        out: BufWriter<std::fs::File>,\n        first_frame: u64,\n        remaining: usize,\n    }\n    static TRACE: OnceLock<Option<Mutex<Trace>>> = OnceLock::new();\n    let Some(trace) = TRACE.get_or_init(|| {\n        let path = std::env::var_os(\"VICTORY_PAGE_TRACE\")?;\n        let out = match std::fs::File::create(path) {\n            Ok(file) => BufWriter::new(file),\n            Err(error) => {\n                tracing::warn!(%error, \"cannot open page mapping trace\");\n                return None;\n            }\n        };\n        let first_frame = std::env::var(\"VICTORY_PAGE_TRACE_AFTER\")\n            .ok()\n            .and_then(|value| value.parse().ok())\n            .unwrap_or(0);\n        Some(Mutex::new(Trace { out, first_frame, remaining: 65_536 }))\n    }) else {\n        return;\n    };\n    let frame = presented();\n    let mut trace = trace.lock().unwrap_or_else(|e| e.into_inner());\n    if trace.remaining == 0 || frame < trace.first_frame {\n        return;\n    }\n    let mut at = destination;\n    for range in ranges.iter().take(trace.remaining) {\n        if writeln!(\n            trace.out, \"{frame},{at},{pool},{pool_pages},{},{},{}\",\n            range.kind, range.start, range.count\n        ).is_err() {\n            trace.remaining = 0;\n            return;\n        }\n        trace.remaining -= 1;\n        at += u64::from(range.count) * PAGE;\n    }\n    if let Err(error) = trace.out.flush() {\n        tracing::warn!(%error, \"cannot flush page mapping trace\");\n        trace.remaining = 0;\n    }\n}\n\n/// `CopyPageMappingsBatchX(count, batches, pool, pool pages, flags)`: maps\n/// pages of a pool (memory the title mapped physical pages into) at the\n/// batches' addresses. The title streams textures into pool pages"),
    ("        }\n        // SAFETY: each batch holds `count` ranges.\n        let ranges = unsafe { std::slice::from_raw_parts(b.ranges, b.count as usize) };\n        let mut at = b.destination;\n        for r in ranges {\n            let len = u64::from(r.count) * PAGE;",
     "        }\n        // SAFETY: each batch holds `count` ranges.\n        let ranges = unsafe { std::slice::from_raw_parts(b.ranges, b.count as usize) };\n        #[cfg(feature = \"diagnostics\")]\n        trace_page_ranges(b.destination, pool, pool_pages, ranges);\n        let mut at = b.destination;\n        for r in ranges {\n            let len = u64::from(r.count) * PAGE;"),
)
MODULE = "\n#[cfg(test)]\n#[path = \"xmem_tile_replay.rs\"]\nmod tile_replay;\n"

def transform(source):
    for old, new in REPLACEMENTS:
        if source.count(old) != 1:
            raise ValueError("Expected exactly one pinned queue anchor")
        source = source.replace(old, new, 1)
    return source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    root = args.checkout
    try:
        queue, xmem, fixture = (root / p for p in (QUEUE, XMEM, FIXTURE))
        new_queue = transform(queue.read_text(encoding="utf-8"))
        old_xmem = xmem.read_text(encoding="utf-8")
        model = root / MODEL
        if model.exists() or fixture.exists() or "mod tile_replay;" in old_xmem:
            raise ValueError("Tile replay already present")
        fixture_source = Path(__file__).resolve().with_name("paired_tile_replay.rs").read_text(encoding="utf-8")
        model_source = (Path(__file__).resolve().parents[1] / "probes" / "software_pages.rs").read_text(encoding="utf-8")
        queue.write_text(new_queue, encoding="utf-8")
        xmem.write_text(old_xmem + MODULE + '\n#[cfg(test)]\n#[path = "xmem_software_pages.rs"]\nmod software_pages;\n', encoding="utf-8")
        fixture.write_text(fixture_source, encoding="utf-8")
        model.write_text(model_source, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Tile replay preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
