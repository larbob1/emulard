#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pipeline scheduling candidates and cache publication correctness fixes."""
import argparse
from pathlib import Path

PATCHES = {
    "crates/victory-gpu/src/pipeline/make.rs": (
        ("    fn pop(&mut self) -> Option<Arc<Pending>> {\n",
         "    fn pop(&mut self) -> Option<Arc<Pending>> {\n        self.pop_with_burst(graphics_burst())\n    }\n\n    fn pop_with_burst(&mut self, burst: Option<usize>) -> Option<Arc<Pending>> {\n"),
        ("    requested: VecDeque<Arc<Pending>>,\n}",
         "    requested: VecDeque<Arc<Pending>>,\n    graphics_streak: usize,\n}"),
        ("            requested: VecDeque::new(),\n        }",
         "            requested: VecDeque::new(),\n            graphics_streak: 0,\n        }"),
        ("        let p = self\n            .requested_graphics\n            .pop_front()\n            .or_else(|| self.requested.pop_front())\n            .or_else(|| {\n                // An early entry can have been promoted and claimed already.\n                std::iter::from_fn(|| self.early.pop_front())\n                    .find(|p| p.queue_state.load(Ordering::Relaxed) == EARLY)\n            })?;",
         "        // Preserve vertex priority, but optionally give requested\n        // compute/mesh work a turn after a bounded graphics burst.\n        let prefer_other = burst.is_some_and(|limit| {\n            self.graphics_streak >= limit && !self.requested.is_empty()\n        });\n        let p = if prefer_other {\n            self.graphics_streak = 0;\n            self.requested.pop_front()\n        } else if let Some(p) = self.requested_graphics.pop_front() {\n            self.graphics_streak = self.graphics_streak.saturating_add(1);\n            Some(p)\n        } else if let Some(p) = self.requested.pop_front() {\n            self.graphics_streak = 0;\n            Some(p)\n        } else {\n            self.graphics_streak = 0;\n            // An early entry can have been promoted and claimed already.\n            std::iter::from_fn(|| self.early.pop_front())\n                .find(|p| p.queue_state.load(Ordering::Relaxed) == EARLY)\n        }?;"),
        ("/// Starts the workers (half the logical processors, 2 to 8) on first use.",
         "fn bounded_setting(raw: Option<&str>, min: usize, max: usize) -> Option<usize> {\n    raw.and_then(|s| s.trim().parse::<usize>().ok()).filter(|&n| n >= min && n <= max)\n}\n\nfn graphics_burst() -> Option<usize> {\n    static BURST: OnceLock<Option<usize>> = OnceLock::new();\n    *BURST.get_or_init(|| bounded_setting(std::env::var(\"VICTORY_PIPELINE_GRAPHICS_BURST\").ok().as_deref(), 1, 128))\n}\n\nfn worker_count(default: usize) -> usize {\n    bounded_setting(std::env::var(\"VICTORY_PIPELINE_WORKERS\").ok().as_deref(), 1, 8).unwrap_or(default)\n}\n\n#[cfg(test)]\nmod perf5_queue_tests {\n    use super::*;\n    #[test]\n    fn bounded_burst_yields_to_requested_other_work() {\n        let mut q = Queue::new();\n        let other = Arc::new(Pending::new(Vec::new(), None));\n        other.queue_state.store(REQUESTED, Ordering::Relaxed);\n        q.requested.push_back(other.clone());\n        let graphics: Vec<_> = (0..4).map(|_| Arc::new(Pending::new(Vec::new(), None))).collect();\n        for p in &graphics {\n            p.queue_state.store(REQUESTED, Ordering::Relaxed);\n            q.requested_graphics.push_back(p.clone());\n        }\n        assert!(Arc::ptr_eq(&q.pop_with_burst(Some(2)).unwrap(), &graphics[0]));\n        assert!(Arc::ptr_eq(&q.pop_with_burst(Some(2)).unwrap(), &graphics[1]));\n        assert!(Arc::ptr_eq(&q.pop_with_burst(Some(2)).unwrap(), &other));\n        assert!(Arc::ptr_eq(&q.pop_with_burst(Some(2)).unwrap(), &graphics[2]));\n        assert!(Arc::ptr_eq(&q.pop_with_burst(Some(2)).unwrap(), &graphics[3]));\n        assert!(q.pop_with_burst(Some(2)).is_none());\n    }\n\n    #[test]\n    fn bounded_worker_settings() {\n        assert_eq!(bounded_setting(Some(\" 4 \"), 1, 8), Some(4));\n        for raw in [None, Some(\"0\"), Some(\"9\"), Some(\"-1\"), Some(\"bad\")] {\n            assert_eq!(bounded_setting(raw, 1, 8), None);\n        }\n    }\n}\n\n/// Starts the workers (half the logical processors, 2 to 8) on first use."),
        ("        let workers = std::thread::available_parallelism().map_or(2, |n| (n.get() / 2).clamp(2, 8));",
         "        let default = std::thread::available_parallelism().map_or(2, |n| (n.get() / 2).clamp(2, 8));\n        let workers = worker_count(default);\n        tracing::info!(workers, graphics_burst = ?graphics_burst(), \"pipeline worker configuration\");"),
    ),
    "crates/victory-gpu/src/pipeline/library.rs": (
        ("    static LAST: Mutex<Option<std::time::Instant>> = Mutex::new(None);\n    const SAVE_EVERY",
         "    // Own the temporary file, rename and early-list publication as one\n    // process-local operation. Periodic callers never queue behind a save.\n    static SAVE_GATE: Mutex<()> = Mutex::new(());\n    let _save = if now {\n        SAVE_GATE.lock().unwrap_or_else(|e| e.into_inner())\n    } else {\n        match SAVE_GATE.try_lock() {\n            Ok(g) => g,\n            Err(std::sync::TryLockError::Poisoned(e)) => e.into_inner(),\n            Err(std::sync::TryLockError::WouldBlock) => return,\n        }\n    };\n    static LAST: Mutex<Option<std::time::Instant>> = Mutex::new(None);\n    const SAVE_EVERY"),
        ("    let bytes = {\n        let _all = one_call();\n        // No store between asking the size and writing; loads go on.",
         "    let (bytes, saved_added) = {\n        let _all = one_call();\n        // No store between asking the size and writing; loads go on."),
        ("        if added == 0 {\n            0\n        } else {",
         "        if added == 0 {\n            (0, 0)\n        } else {"),
        ("                let _ = std::fs::remove_file(&tmp);\n                return;\n            }\n            library.added.store(0, Ordering::Relaxed);\n            SAVED.store(size as u64, Ordering::Relaxed);\n            size",
         "                let _ = std::fs::remove_file(&tmp);\n                // Do not lose a pending early-list update on serialization failure.\n                USED_CHANGED.store(true, Ordering::Relaxed);\n                return;\n            }\n            library.added.store(0, Ordering::Relaxed);\n            (size, added)"),
        ("    let library_written = if bytes > 0 { replace_library(dir, &tmp) } else { Ok(()) };\n    if bytes > 0 && library_written.is_ok() {",
         "    let library_written = if bytes > 0 { replace_library(dir, &tmp) } else { Ok(()) };\n    if library_written.is_err() {\n        // Stores may have happened after serialization. Add back only the\n        // captured count; never overwrite newer dirty bookkeeping.\n        library.added.fetch_add(saved_added, Ordering::Relaxed);\n    } else if bytes > 0 {\n        SAVED.store(bytes as u64, Ordering::Relaxed);\n    }\n    if bytes > 0 && library_written.is_ok() {"),
        ("        Err(e) => tracing::warn!(error = %e, \"host pipeline library not saved\"),",
         "        Err(e) => {\n            // Re-attempt both failed early-list writes and library publication.\n            USED_CHANGED.store(true, Ordering::Relaxed);\n            tracing::warn!(error = %e, \"host pipeline library not saved\");\n        }"),
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
        parser.exit(1, f"Pipeline performance preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
