#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare opt-in bounded texture snapshots on the paired-wave runtime."""
import argparse
from pathlib import Path

PATCHES = {
    "crates/victory-gpu/src/watch.rs": (
        ("static MAPPING: std::sync::RwLock<()> = std::sync::RwLock::new(());",
         "static MAPPING: std::sync::RwLock<()> = std::sync::RwLock::new(());\n// Epoch changes at both boundaries of a remap. Only used by opt-in\n// texture snapshots; the existing read guard remains the safety boundary.\nstatic MAPPING_EPOCH: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);\n\npub(crate) fn mapping_epoch() -> u64 {\n    MAPPING_EPOCH.load(std::sync::atomic::Ordering::SeqCst)\n}"),
        ("        crate::framelog::add(crate::framelog::T::RemapUs, self.1.elapsed().as_micros() as u64);",
         "        MAPPING_EPOCH.fetch_add(1, std::sync::atomic::Ordering::SeqCst);\n        crate::framelog::add(crate::framelog::T::RemapUs, self.1.elapsed().as_micros() as u64);"),
        ("    let held = MAPPING.write().unwrap_or_else(|e| e.into_inner());\n    crate::framelog::add(crate::framelog::T::Remaps, 1);",
         "    let held = MAPPING.write().unwrap_or_else(|e| e.into_inner());\n    MAPPING_EPOCH.fetch_add(1, std::sync::atomic::Ordering::SeqCst);\n    crate::framelog::add(crate::framelog::T::Remaps, 1);"),
    ),
    "crates/victory-gpu/src/texture.rs": (
        ("fn through_copy() -> bool {",
         "fn short_snapshot() -> bool {\n    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    *ON.get_or_init(|| std::env::var_os(\"VICTORY_TEXTURE_SHORT_LOCK\").is_some_and(|v| v == \"1\"))\n}\n\n// Cap extra per-worker scratch growth. Keep the original path for\n// larger textures, partly mapped textures and on-demand mip judgement.\nconst SHORT_SNAPSHOT_MAX: usize = 8 * 1024 * 1024;\n\n// Cumulative diagnostics, emitted at powers of two. Work times are\n// summed across threads and cannot be added to frame wall time.\nfn snapshot_counts(bytes: usize, copy_us: u64, unlocked_us: u64, retry: bool) {\n    use std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n    static CALLS: AtomicU64 = AtomicU64::new(0);\n    static BYTES: AtomicU64 = AtomicU64::new(0);\n    static COPY: AtomicU64 = AtomicU64::new(0);\n    static UNLOCKED_US: AtomicU64 = AtomicU64::new(0);\n    static RETRIES: AtomicU64 = AtomicU64::new(0);\n    BYTES.fetch_add(bytes as u64, Relaxed);\n    COPY.fetch_add(copy_us, Relaxed);\n    UNLOCKED_US.fetch_add(unlocked_us, Relaxed);\n    RETRIES.fetch_add(u64::from(retry), Relaxed);\n    let calls = CALLS.fetch_add(1, Relaxed) + 1;\n    if calls.is_power_of_two() {\n        tracing::info!(\n            calls, bytes = BYTES.load(Relaxed), copy_us = COPY.load(Relaxed),\n            unlocked_us = UNLOCKED_US.load(Relaxed), retries = RETRIES.load(Relaxed),\n            \"texture short-lock totals\"\n        );\n    }\n}\n\nfn through_copy() -> bool {"),
        ("        if through_copy() {\n            return with_title(self.memory, size, |tiled| {",
         "        // Snapshot only the fully mapped, non-on-demand path. Capture\n        // under the established read guard; release it before expensive\n        // hashing and detiling. Never dereference title memory after drop.\n        if short_snapshot() && !self.on_demand && size != 0 && size <= SHORT_SNAPSHOT_MAX && !through_copy() {\n            let epoch = crate::watch::mapping_epoch();\n            let copy_started = std::time::Instant::now();\n            return with_read(size, |read| {\n                let copied = crate::host::read_into(self.memory, read);\n                drop(_mapped);\n                let copy_us = copy_started.elapsed().as_micros() as u64;\n                let work_started = std::time::Instant::now();\n                if !copied {\n                    last.asked = 0;\n                    snapshot_counts(0, copy_us, 0, true);\n                    return 0;\n                }\n                let hash = blake3::hash(read);\n                // A remap started after the snapshot was captured.\n                // Do not publish this candidate; force a future refresh.\n                if crate::watch::mapping_epoch() != epoch {\n                    last.asked = 0;\n                    snapshot_counts(size, copy_us, work_started.elapsed().as_micros() as u64, true);\n                    return size;\n                }\n                #[cfg(feature = \"diagnostics\")]\n                crate::copystat::add(crate::copystat::C::TexHashed, size as u64);\n                if last.hash != Some(hash) {\n                    last.hash = Some(hash);\n                    self.detile(read);\n                    #[cfg(feature = \"diagnostics\")]\n                    crate::copystat::add(crate::copystat::C::TexChanged, size as u64);\n                }\n                // A remap during detile cannot invalidate the owned bytes,\n                // but this snapshot may now be old. Retry rather than\n                // treating it as the latest generation on the next check.\n                let retry = crate::watch::mapping_epoch() != epoch;\n                if retry {\n                    last.asked = 0;\n                    last.hash = None;\n                }\n                snapshot_counts(size, copy_us, work_started.elapsed().as_micros() as u64, retry);\n                size\n            });\n        }\n        if through_copy() {\n            return with_title(self.memory, size, |tiled| {"),
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
        # Validate all anchors before modifying either source file.
        changes = {}
        for relative, replacements in PATCHES.items():
            path = args.checkout / relative
            changes[path] = transform(path.read_text(encoding="utf-8"), replacements)
        for path, content in changes.items():
            path.write_text(content, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Texture snapshot preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
