#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the opt-in observational pinned backing mirror."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/xmem.rs")
REPLACEMENTS = (
    ("    vacant_pages: std::collections::BTreeSet<usize>,",
     "    vacant_pages: std::collections::BTreeSet<usize>,\n    // Diagnostic mirror only. A mismatch disables it for the process.\n    pinned_mirror: pinned_views::PinnedViews<Section>,\n    mirror_failed: bool,"),
    ("fn reuse_placeholders() -> bool {",
     "#[path = \"xmem_pinned_views.rs\"]\nmod pinned_views;\n\nfn mirror_enabled() -> bool {\n    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    *ON.get_or_init(|| std::env::var_os(\"VICTORY_MAP_PINNED_MIRROR\").is_some_and(|v| v == \"1\"))\n}\n\nfn mirror_record(physical: &mut Physical, base: usize, len: usize, slice: &Slice) {\n    if !mirror_enabled() || physical.mirror_failed { return; }\n    let ok = slice.index.checked_mul(PAGE).is_some_and(|offset|\n        physical.pinned_mirror.insert(base, len, slice.section.clone(), offset));\n    if !ok { mirror_disable(physical); return; }\n    mirror_counts(true);\n}\n\nfn mirror_remove(physical: &mut Physical, base: usize, len: usize) {\n    if !mirror_enabled() || physical.mirror_failed { return; }\n    if !physical.pinned_mirror.remove_exact(base, len) {\n        mirror_disable(physical);\n        return;\n    }\n    mirror_counts(false);\n}\n\nfn mirror_disable(physical: &mut Physical) {\n    physical.mirror_failed = true;\n    physical.pinned_mirror = Default::default();\n    tracing::warn!(\"pinned mapping mirror disabled after inconsistent event\");\n}\n\nfn mirror_counts(mapped: bool) {\n    use std::sync::atomic::{AtomicU64, Ordering};\n    static MAPS: AtomicU64 = AtomicU64::new(0);\n    static UNMAPS: AtomicU64 = AtomicU64::new(0);\n    let count = if mapped { &MAPS } else { &UNMAPS };\n    if (count.fetch_add(1, Ordering::Relaxed) + 1).is_power_of_two() {\n        tracing::info!(maps = MAPS.load(Ordering::Relaxed), unmaps = UNMAPS.load(Ordering::Relaxed), \"pinned mapping mirror totals\");\n    }\n}\n\nfn reuse_placeholders() -> bool {"),
    ("    physical.views.insert(base, (len, slice));",
     "    mirror_record(physical, base, len, &slice);\n    physical.views.insert(base, (len, slice));"),
    ("        physical.views.remove(&at);\n        for k in 0..size.div_ceil(PAGE) {",
     "        physical.views.remove(&at);\n        mirror_remove(physical, at, size);\n        for k in 0..size.div_ceil(PAGE) {"),
    ("        // Inject a failed host unmap without removing the actual view.",
     "        // Compare the live mirror against the authoritative view map.\n        // The plan pins sections, not the mutable contents of their pages.\n        if mirror_enabled() {\n            let physical = physical();\n            assert!(!physical.mirror_failed);\n            let spans = physical.pinned_mirror.resolve(a as usize, 3 * PAGE).unwrap();\n            for (index, span) in spans.iter().enumerate() {\n                assert!(span.len > 0, \"empty mirror span {index}\");\n            }\n            for k in 0..3 {\n                let at = a as usize + k * PAGE;\n                let want = shown_slice(&physical, at).unwrap();\n                let got = physical.pinned_mirror.resolve(at, PAGE).unwrap();\n                assert_eq!(got.len(), 1);\n                assert!(Arc::ptr_eq(&got[0].section, &want.section));\n                assert_eq!(got[0].offset, want.index * PAGE);\n            }\n        }\n\n        // Inject a failed host unmap without removing the actual view."),
    ("            assert!(same_slice(&before, &shown_slice(&physical, a as usize).unwrap()));",
     "            assert!(same_slice(&before, &shown_slice(&physical, a as usize).unwrap()));\n            if mirror_enabled() {\n                assert!(!physical.mirror_failed);\n                let plan = physical.pinned_mirror.resolve(a as usize, PAGE).unwrap();\n                assert!(Arc::ptr_eq(&plan[0].section, &before.section));\n                assert_eq!(plan[0].offset, before.index * PAGE);\n            }"),
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
    module = path.with_name("xmem_pinned_views.rs")
    fixture = path.with_name("xmem_pinned_backing_tests.rs")
    try:
        if module.exists() or fixture.exists():
            raise ValueError("Pinned mirror already installed")
        new_source = transform(path.read_text(encoding="utf-8"))
        helper = (Path(__file__).resolve().parents[1] / "probes" / "pinned_views.rs").read_text(encoding="utf-8")
        fixture_source = Path(__file__).resolve().with_name("pinned_backing_tests.rs").read_text(encoding="utf-8")
        new_source += '\n#[cfg(test)]\n#[path = "xmem_pinned_backing_tests.rs"]\nmod pinned_backing_tests;\n'
        path.write_text(new_source, encoding="utf-8")
        module.write_text(helper, encoding="utf-8")
        fixture.write_text(fixture_source, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Pinned mirror preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
