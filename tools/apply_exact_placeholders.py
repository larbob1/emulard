#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install opt-in exact multi-page placeholder hints."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/xmem.rs")
REPLACEMENTS = (
    ("    vacant_pages: std::collections::BTreeSet<usize>,",
     "    vacant_pages: std::collections::BTreeSet<usize>,\n    // Advisory only: host replacement still validates exact ranges.\n    exact_placeholders: placeholder_hints::ExactHints,"),
    ("fn reuse_placeholders() -> bool {",
     "#[path = \"xmem_placeholder_hints.rs\"]\nmod placeholder_hints;\n\nfn exact_placeholders_on() -> bool {\n    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    *ON.get_or_init(|| std::env::var_os(\"VICTORY_MAP_EXACT_PLACEHOLDERS\").is_some_and(|v| v == \"1\"))\n}\n\nfn exact_placeholder_counts(hit: bool) {\n    use std::sync::atomic::{AtomicU64, Ordering};\n    static ATTEMPTS: AtomicU64 = AtomicU64::new(0);\n    static HITS: AtomicU64 = AtomicU64::new(0);\n    if hit { HITS.fetch_add(1, Ordering::Relaxed); }\n    let attempts = ATTEMPTS.fetch_add(1, Ordering::Relaxed) + 1;\n    if attempts.is_power_of_two() {\n        tracing::info!(attempts, hits = HITS.load(Ordering::Relaxed), \"exact placeholder totals\");\n    }\n}\n\nfn reuse_placeholders() -> bool {"),
    ("    const MEM_COALESCE_PLACEHOLDERS: u32 = 1;\n    if pages > 1 {",
     "    const MEM_COALESCE_PLACEHOLDERS: u32 = 1;\n    if pages > 1 {\n        // A successfully preserved, exact multi-page view may already be\n        // one placeholder. Do not split it merely to coalesce it again.\n        if exact_placeholders_on() {\n            let bytes = pages * PAGE;\n            if physical.exact_placeholders.contains(base, bytes)\n                && map(physical, base, bytes, slice.clone())\n            {\n                alias_line([0, 0, 0, 1, 0]);\n                return true;\n            }\n            // Splitting/coalescing below changes placeholder boundaries.\n            physical.exact_placeholders.discard(base, bytes);\n        }"),
    ("    let reuse = len == PAGE && physical.vacant_pages.remove(&base) && reuse_placeholders();",
     "    let exact = exact_placeholders_on() && physical.exact_placeholders.take(base, len);\n    let reuse = len == PAGE && physical.vacant_pages.remove(&base) && reuse_placeholders();"),
    ("    if reuse {\n        view = replace();\n        if view.Value as usize == base {",
     "    if exact || reuse {\n        view = replace();\n        if exact {\n            exact_placeholder_counts(view.Value as usize == base);\n        }\n        if view.Value as usize == base {"),
    ("        physical.views.remove(&at);\n        for k in 0..size.div_ceil(PAGE) {",
     "        physical.views.remove(&at);\n        // Only a successful preserve-placeholder unmap supplies a hint.\n        // Any later overlapping map consumes it; a stale hint can never\n        // authorize a read or bypass the host replacement check.\n        if exact_placeholders_on() {\n            physical.exact_placeholders.record(at, size);\n        }\n        for k in 0..size.div_ceil(PAGE) {"),
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
    module = path.with_name("xmem_placeholder_hints.rs")
    try:
        if module.exists():
            raise ValueError("Placeholder hint module already installed")
        new_source = transform(path.read_text(encoding="utf-8"))
        helper = (Path(__file__).resolve().parents[1] / "probes" / "placeholder_hints.rs").read_text(encoding="utf-8")
        path.write_text(new_source, encoding="utf-8")
        module.write_text(helper, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Exact placeholder preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
