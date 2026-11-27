#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in DirectStorage concurrency cap for paired-wave runtime."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/dstorage.rs")
REPLACEMENTS = (
    ("        let workers = std::thread::available_parallelism().map_or(4, |n| n.get());",
     "        let default = std::thread::available_parallelism().map_or(4, |n| n.get());\n        let workers = disk_worker_count(default, std::env::var(\"VICTORY_DISK_WORKERS\").ok().as_deref());\n        tracing::info!(workers, default, \"dstorage: worker configuration\");"),
    ("impl Scheduler {\n    fn lock(&self) -> MutexGuard<'_, Lanes> {",
     "// Preserve automatic behavior when unset. Explicit settings cap concurrency,\n// never enlarge it beyond the host's available parallelism.\nfn disk_worker_count(default: usize, setting: Option<&str>) -> usize {\n    setting.and_then(|s| s.trim().parse::<usize>().ok())\n        .filter(|&n| n > 0).map_or(default, |n| n.min(default))\n}\n\n#[cfg(test)]\nmod perf6_worker_tests {\n    use super::disk_worker_count;\n    #[test]\n    fn cap_does_not_expand_or_disable_workers() {\n        assert_eq!(disk_worker_count(16, None), 16);\n        assert_eq!(disk_worker_count(16, Some(\"4\")), 4);\n        assert_eq!(disk_worker_count(2, Some(\"8\")), 2);\n        assert_eq!(disk_worker_count(16, Some(\"0\")), 16);\n        assert_eq!(disk_worker_count(16, Some(\"bad\")), 16);\n    }\n}\n\nimpl Scheduler {\n    fn lock(&self) -> MutexGuard<'_, Lanes> {"),
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
        parser.exit(1, f"Disk worker preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
