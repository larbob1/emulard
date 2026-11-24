#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned builder preparation and memory budget candidate."""
import argparse
from pathlib import Path
import sys
from apply_memory_patch import blob_hash

SPECS = [["crates/victory-gpu/src/pipeline.rs","60ed05c0c9b169535aff1256cc3443c9ada8dbcc",[["    static ALLOWED: OnceLock<bool> = OnceLock::new();\n    if !*ALLOWED.get_or_init(|| std::env::var_os(\"VICTORY_BVH_BUILDER\").is_some_and(|v| v == \"1\")) {","    if !builder_requested() {"],["/// At a dispatch of a builder pipeline: whether the builder runs (see","/// The existing opt-in also controls early preparation.\n#[cfg(windows)]\nfn builder_requested() -> bool {\n    static ALLOWED: OnceLock<bool> = OnceLock::new();\n    *ALLOWED.get_or_init(|| std::env::var_os(\"VICTORY_BVH_BUILDER\").is_some_and(|v| v == \"1\"))\n}\n\n/// At a dispatch of a builder pipeline: whether the builder runs (see"],["        let mut b = BUILDER.lock().unwrap_or_else(|e| e.into_inner());\n        b.pipelines.push(host.clone());\n        b.whole = false;","        {\n            let mut b = BUILDER.lock().unwrap_or_else(|e| e.into_inner());\n            b.pipelines.push(host.clone());\n            b.whole = false;\n        }\n        // Queue compilation outside the builder lock; the all-or-none\n        // dispatch gate remains authoritative.\n        if builder_requested() {\n            make::prepare_builder(&host);\n        }"],["    let missing = b.pipelines.iter().filter(|p| !make::now(p)).count();","    let mut missing = 0;\n    for p in &b.pipelines {\n        if !make::now(p) {\n            missing += 1;\n            make::report_builder_failure(p);\n        }\n    }"]]],["crates/victory-gpu/src/pipeline/make.rs","98624460520e9b66d0691e886620d3d51f71c05f",[["/// At the title's creation of a pipeline: starts it at once if an earlier","/// Prepare an opted-in builder stage on an existing compiler worker.\npub(crate) fn prepare_builder(p: &Arc<Pending>) {\n    if p.made.get().is_none() {\n        start(p, EARLY);\n    }\n}\n\n/// Distinguish translation failure from host pipeline rejection without\n/// logging source, memory contents or per-user paths.\npub(crate) fn report_builder_failure(p: &Pending) {\n    let untranslated = p.shaders.iter()\n        .filter(|s| matches!(s.translated.get(), Some(None)))\n        .count();\n    tracing::warn!(untranslated, stages = p.shaders.len(),\n        \"builder pipeline unavailable; safety gate retained\");\n}\n\n/// At the title's creation of a pipeline: starts it at once if an earlier"],["        let workers = std::thread::available_parallelism().map_or(2, |n| (n.get() / 2).clamp(2, 8));","        let default = std::thread::available_parallelism().map_or(2, |n| (n.get() / 2).clamp(2, 8));\n        let workers = worker_limit(default, std::env::var(\"EMULARD_PIPELINE_WORKERS\").ok().as_deref());"],["/// Starts the workers (half the logical processors, 2 to 8) on first use.","fn worker_limit(default: usize, setting: Option<&str>) -> usize {\n    setting.and_then(|s| s.trim().parse::<usize>().ok())\n        .map(|n| n.clamp(1, default))\n        .unwrap_or(default)\n}\n\n#[cfg(test)]\nmod worker_limit_tests {\n    use super::worker_limit;\n\n    #[test]\n    fn worker_cap_is_bounded() {\n        assert_eq!(worker_limit(4, None), 4);\n        assert_eq!(worker_limit(4, Some(\"2\")), 2);\n        assert_eq!(worker_limit(4, Some(\"0\")), 1);\n        assert_eq!(worker_limit(4, Some(\"99\")), 4);\n        assert_eq!(worker_limit(4, Some(\"bad\")), 4);\n    }\n}\n\n/// Starts the workers (half the logical processors, 2 to 8) on first use."]]],["crates/victory-gpu/src/resource.rs","2367d8b9943e523f080bbd41581449839512e3d9",[["        mb.trim().parse::<u64>().ok().map(|mb| mb << 20)","        mb.trim().parse::<u64>().ok().and_then(|mb| mb.checked_mul(1 << 20))"],["        return filled < limit;\n    }\n    if filled < FLOOR {","        let budget = crate::host::host().and_then(|h| h.video_memory());\n        return texture_room_with_limit(filled, limit, budget.map(|[total, used, ..]| (total, used)));\n    }\n    if filled < FLOOR {"],["/// Whether more host copies of textures the title fills may be made for","#[cfg(windows)]\nfn texture_room_with_limit(filled: u64, limit: u64, budget: Option<(u64, u64)>) -> bool {\n    filled < limit && budget.is_none_or(|(total, used)| used < total / 10 * 9)\n}\n\n#[cfg(all(test, windows))]\nmod texture_budget_tests {\n    use super::texture_room_with_limit;\n\n    #[test]\n    fn explicit_cap_and_driver_budget_both_apply() {\n        assert!(texture_room_with_limit(10, 20, Some((100, 80))));\n        assert!(!texture_room_with_limit(20, 20, Some((100, 80))));\n        assert!(!texture_room_with_limit(10, 20, Some((100, 90))));\n        assert!(!texture_room_with_limit(10, 20, Some((0, 0))));\n        assert!(texture_room_with_limit(10, 20, None));\n    }\n}\n\n/// Whether more host copies of textures the title fills may be made for"]]]]

def patch_source(data, expected, edits):
    normalized = data.replace(b"\r\n", b"\n")
    if blob_hash(normalized) != expected:
        raise ValueError("Unexpected source revision.")
    text = normalized.decode("utf-8")
    for before, after in edits:
        if text.count(before) != 1:
            raise ValueError("Source anchor differs.")
        text = text.replace(before, after)
    updated = text.encode("utf-8")
    return updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.checkout.resolve()
    try:
        if not (root / ".git").exists():
            raise ValueError("Use a separate Git checkout.")
        pending = {}
        for path, expected, edits in SPECS:
            target = root / path
            if target.resolve() != target or not target.is_file():
                raise ValueError("Invalid source path.")
            pending[target] = patch_source(target.read_bytes(), expected, edits)
        if args.apply:
            for target, data in pending.items():
                target.write_bytes(data)
            print("Builder and budget candidate applied.")
        else:
            print("Sources validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
