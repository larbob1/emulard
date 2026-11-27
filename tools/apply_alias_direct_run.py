#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Try the normal contiguous map before alias-run placeholder coalescing."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/xmem.rs")
REPLACEMENTS = (
    ("fn alias_runs() -> bool {",
     "// An independent experiment for alias runs: many destination ranges are\n// already backed by a single placeholder after unmapping. Try replacing\n// that range before map_run splits it into pages and coalesces it again.\nfn alias_direct_on() -> bool {\n    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    *ON.get_or_init(|| std::env::var_os(\"VICTORY_MAP_ALIAS_DIRECT\").is_some_and(|v| v == \"1\"))\n}\n\nfn alias_direct_counts(hit: bool) {\n    use std::sync::atomic::{AtomicU64, Ordering};\n    static ATTEMPTS: AtomicU64 = AtomicU64::new(0);\n    static HITS: AtomicU64 = AtomicU64::new(0);\n    if hit { HITS.fetch_add(1, Ordering::Relaxed); }\n    let attempts = ATTEMPTS.fetch_add(1, Ordering::Relaxed) + 1;\n    if attempts.is_power_of_two() {\n        tracing::info!(attempts, hits = HITS.load(Ordering::Relaxed), \"alias direct run totals\");\n    }\n}\n\nfn alias_runs() -> bool {"),
    ("            if !map_run(physical, at, end - k, &wanted[k]) {\n                return false;\n            }",
     "            let direct = if end - k > 1 && alias_direct_on() {\n                let hit = map(physical, at, bytes, wanted[k].clone());\n                alias_direct_counts(hit);\n                if hit {\n                    alias_line([0, 0, 0, 1, 0]);\n                }\n                hit\n            } else {\n                false\n            };\n            if !direct && !map_run(physical, at, end - k, &wanted[k]) {\n                return false;\n            }"),
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
        parser.exit(1, f"Alias direct-run preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
