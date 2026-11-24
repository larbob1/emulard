#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare a revision-pinned experimental memory scheduling patch."""
import argparse
import hashlib
from pathlib import Path
import sys

HOST = "crates/victory-gpu/src/host.rs"
MEMORY = "crates/victory-gpu/src/memory.rs"
EXPECTED = {
    HOST: "cb57a59f989dfa21eb6bbd0b60abe2042c5041fe",
    MEMORY: "c25636783511fdfbf9692fdd36ef150f69ea666e",
}
TRACKER = "#[derive(Default)]\nstruct RawCopyProgress {\n    read_count: Option<usize>,\n    write_count: usize,\n    kept: bool,\n}\n\nimpl RawCopyProgress {\n    fn invalidate_reads(&mut self) {\n        self.read_count = None;\n    }\n\n    fn schedule(&mut self, count: usize, writes: bool) -> (usize, usize, bool) {\n        let first = !self.kept;\n        self.kept = true;\n        let read_from = self.read_count.unwrap_or(0);\n        self.read_count = Some(count);\n        let write_from = if writes {\n            let previous = self.write_count;\n            self.write_count = count;\n            previous\n        } else {\n            count\n        };\n        (read_from, write_from, first)\n    }\n}\n\n#[cfg(test)]\nmod raw_copy_progress_tests {\n    use super::RawCopyProgress;\n\n    #[test]\n    fn interleaved_lists() {\n        let mut a = RawCopyProgress::default();\n        let mut b = RawCopyProgress::default();\n        assert_eq!(a.schedule(2, true), (0, 0, true));\n        assert_eq!(b.schedule(3, true), (0, 0, true));\n        assert_eq!(a.schedule(3, true), (2, 2, false));\n        assert_eq!(a.schedule(3, true), (3, 3, false));\n    }\n\n    #[test]\n    fn read_only_then_write() {\n        let mut a = RawCopyProgress::default();\n        assert_eq!(a.schedule(2, false), (0, 2, true));\n        assert_eq!(a.schedule(4, true), (2, 0, false));\n        assert_eq!(a.schedule(5, false), (4, 5, false));\n        assert_eq!(a.schedule(5, true), (5, 4, false));\n    }\n\n    #[test]\n    fn title_writes_invalidate_reads_without_redeclaring_writes() {\n        let mut a = RawCopyProgress::default();\n        assert_eq!(a.schedule(3, true), (0, 0, true));\n        a.invalidate_reads();\n        assert_eq!(a.schedule(4, true), (0, 3, false));\n        assert_eq!(a.schedule(4, true), (4, 4, false));\n    }\n\n    #[test]\n    fn empty_then_reset() {\n        let mut a = RawCopyProgress::default();\n        assert_eq!(a.schedule(0, false), (0, 0, true));\n        assert_eq!(a.schedule(0, false), (0, 0, false));\n        assert_eq!(a.schedule(1, true), (0, 0, false));\n        a = RawCopyProgress::default();\n        assert_eq!(a.schedule(1, true), (0, 0, true));\n    }\n}\n\n"
METHOD = "    /// Track the append-only raw memory directory independently per list.\n    pub(crate) fn raw_copy_schedule(&self, count: usize, writes: bool) -> (usize, usize, bool) {\n        self.deferred().raw_copy_progress.schedule(count, writes)\n    }\n\n"
SCHEDULE = "    let (read_from, write_from, first_read) = list.raw_copy_schedule(m.copies.len(), writes);\n    for (n, shadow) in m.copies.iter().enumerate().skip(read_from.min(write_from)) {\n        let (start, len) = shadow.span();\n        if n >= read_from {\n            shadow.refresh(list, start, len);\n        }\n        if n >= write_from {\n            shadow.gpu_writes(list, start, len);\n        }\n    }\n"

def blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def patch_source(path, data):
    normalized = data.replace(b"\r\n", b"\n")
    if blob_hash(normalized) != EXPECTED[path]:
        raise ValueError(f"{path}: unexpected revision")
    lines = normalized.decode("utf-8").splitlines(keepends=True)
    if path == HOST:
        lines[5053:5053] = [METHOD]
        lines[1604:1604] = [TRACKER]
        lines[1592:1592] = ["    raw_copy_progress: RawCopyProgress,\n"]
        # Preserve the existing deferred-copy invalidation semantics.
        for i in range(len(lines) - 1, -1, -1):
            if lines[i] == "        deferred.refreshed.clear();\n":
                lines.insert(i + 1, "        deferred.raw_copy_progress.invalidate_reads();\n")
        original = "        self.deferred().copies.push(Step::Run(Box::new(work)));\n        self.deferred().refreshed.clear();\n"
        replacement = "        let mut deferred = self.deferred();\n        deferred.copies.push(Step::Run(Box::new(work)));\n        deferred.refreshed.clear();\n        deferred.raw_copy_progress.invalidate_reads();\n"
        combined = "".join(lines)
        if combined.count(original) == 1:
            lines = [combined.replace(original, replacement)]

    else:
        lines[292:309] = [SCHEDULE]
        del lines[259]
    updated = "".join(lines).encode("utf-8")
    return updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated

# Applied after the memory scheduling edits because both target host.rs.
SCRATCH_EDITS = [["const SPARE_MOST: u64 = 128 << 20;","const SPARE_MOST: u64 = 128 << 20;\n\n/// Retention limit for unused upload chunks, independent of live GPU allocations.\nfn spare_limit(value: Option<&str>) -> u64 {\n    value.and_then(|s| s.trim().parse::<u64>().ok())\n        .map(|mb| mb.min(128) << 20)\n        .unwrap_or(SPARE_MOST)\n}\n\nfn spare_most() -> u64 {\n    static LIMIT: OnceLock<u64> = OnceLock::new();\n    *LIMIT.get_or_init(|| spare_limit(std::env::var(\"EMULARD_SCRATCH_IDLE_MB\").ok().as_deref()))\n}\n\n#[cfg(test)]\nmod scratch_limit_tests {\n    use super::{spare_limit, Spare, SPARE_MOST};\n\n    #[test]\n    fn default_and_explicit_limits() {\n        assert_eq!(spare_limit(None), SPARE_MOST);\n        assert_eq!(spare_limit(Some(\"bad\")), SPARE_MOST);\n        assert_eq!(spare_limit(Some(\" 32 \")), 32 << 20);\n        assert_eq!(spare_limit(Some(\"0\")), 0);\n        assert_eq!(spare_limit(Some(\"18446744073709551615\")), SPARE_MOST);\n    }\n\n    #[test]\n    fn returns_unused_chunks_when_budget_is_full() {\n        let mut pool = Spare::new();\n        let limit = spare_limit(Some(\"1\"));\n        assert_eq!(pool.give(1, 1 << 20, limit), None);\n        assert_eq!(pool.give(2, 1, limit), Some(2));\n        assert_eq!(pool.take(1 << 20), Some(1));\n        assert_eq!(pool.give(3, 1, 0), Some(3));\n    }\n\n    #[test]\n    fn rejects_overflow_without_changing_pool() {\n        let mut pool = Spare::new();\n        assert_eq!(pool.give(1, u64::MAX, u64::MAX), None);\n        assert_eq!(pool.give(2, 1, u64::MAX), Some(2));\n        assert_eq!(pool.take(u64::MAX), Some(1));\n    }\n}"],["spare.give(chunk, size, SPARE_MOST)","spare.give(chunk, size, spare_most())"],["if self.bytes + size > most {","if size > most.saturating_sub(self.bytes) {"]]

def patch_scratch(data):
    source = data.decode("utf-8")
    crlf = "\r\n" in source
    source = source.replace("\r\n", "\n")
    for before, after in SCRATCH_EDITS:
        if source.count(before) != 1:
            raise ValueError("Scratch pool source anchor differs.")
        source = source.replace(before, after)
    return (source.replace("\n", "\r\n") if crlf else source).encode("utf-8")

# Applied after the revision-pinned scheduling and idle pool edits.
WRITE_INDEX_EDITS = [["fn declared_writes(runs: &[&HostList]) -> Vec<Declared> {\n    let mut back: Vec<Declared> = Vec::new();\n    for list in runs {\n        for step in &list.deferred().copies {\n            if let Step::GpuWrite(shadow, address, len) = step {\n                let range = (*address, *address + *len);\n                match back.iter_mut().find(|(s, _)| std::sync::Arc::ptr_eq(s, shadow)) {\n                    Some((_, ranges)) => {\n                        if !ranges.contains(&range) {\n                            ranges.push(range);\n                        }\n                    }\n                    None => back.push((shadow.clone(), vec![range])),\n                }\n            }\n        }\n    }\n    back\n}\n","/// Preserve first-seen copy and range order, with constant-time duplicate\n/// detection. Keep overlapping (but not identical) ranges unchanged.\nstruct WriteIndex<K> {\n    groups: Vec<(K, Vec<(usize, usize)>)>,\n    positions: std::collections::HashMap<K, usize>,\n    seen: std::collections::HashSet<(K, usize, usize)>,\n}\n\nimpl<K: Copy + Eq + std::hash::Hash> WriteIndex<K> {\n    fn new() -> Self {\n        Self {\n            groups: Vec::new(),\n            positions: std::collections::HashMap::new(),\n            seen: std::collections::HashSet::new(),\n        }\n    }\n\n    fn add(&mut self, key: K, from: usize, to: usize) {\n        if !self.seen.insert((key, from, to)) {\n            return;\n        }\n        let index = *self.positions.entry(key).or_insert_with(|| {\n            let index = self.groups.len();\n            self.groups.push((key, Vec::new()));\n            index\n        });\n        self.groups[index].1.push((from, to));\n    }\n}\n\n#[cfg(test)]\nmod write_index_tests {\n    use super::WriteIndex;\n\n    #[test]\n    fn retains_first_seen_order_and_overlapping_ranges() {\n        let mut index = WriteIndex::new();\n        for (key, from, to) in [(7, 10, 20), (2, 3, 5), (7, 10, 20),\n                                (7, 15, 25), (2, 3, 5), (2, 8, 9)] {\n            index.add(key, from, to);\n        }\n        assert_eq!(index.groups, vec![(7, vec![(10, 20), (15, 25)]),\n                                      (2, vec![(3, 5), (8, 9)])]);\n    }\n\n    #[test]\n    fn duplicate_heavy_workload() {\n        let mut index = WriteIndex::new();\n        for _ in 0..100 {\n            for key in 0..64 {\n                index.add(key, 0, 65536);\n            }\n        }\n        assert_eq!(index.groups.len(), 64);\n        assert_eq!(index.seen.len(), 64);\n        assert!(index.groups.iter().all(|(_, ranges)| ranges.len() == 1));\n    }\n}\n\nfn declared_writes(runs: &[&HostList]) -> Vec<Declared> {\n    let mut index = WriteIndex::new();\n    let mut copies = std::collections::HashMap::new();\n    for list in runs {\n        for step in &list.deferred().copies {\n            if let Step::GpuWrite(shadow, address, len) = step {\n                let key = std::sync::Arc::as_ptr(shadow) as usize;\n                copies.entry(key).or_insert_with(|| shadow.clone());\n                index.add(key, *address, *address + *len);\n            }\n        }\n    }\n    index.groups.into_iter().map(|(key, ranges)| {\n        (copies.remove(&key).expect(\"indexed copy retained\"), ranges)\n    }).collect()\n}\n"],["        // The ranges this submission's shaders may write, per copy.\n        let mut declared: Vec<(Arc<crate::shadow::Shadow>, Vec<(usize, usize)>)> = Vec::new();\n        for list in runs {\n            for step in &list.deferred().copies {\n                if let Step::GpuWrite(shadow, address, len) = step\n                    && shadow.carded()\n                {\n                    let range = (*address, *address + *len);\n                    match declared.iter_mut().find(|(s, _)| Arc::ptr_eq(s, shadow)) {\n                        Some((_, ranges)) => {\n                            if !ranges.contains(&range) {\n                                ranges.push(range);\n                            }\n                        }\n                        None => declared.push((shadow.clone(), vec![range])),\n                    }\n                }\n            }\n        }\n","        // Use the same first-seen declaration index as CPU writeback.\n        let declared: Vec<Declared> = declared_writes(runs).into_iter()\n            .filter(|(shadow, _)| shadow.carded())\n            .collect();\n"]]

def patch_write_index(data):
    source = data.decode("utf-8")
    crlf = "\r\n" in source
    source = source.replace("\r\n", "\n")
    for before, after in WRITE_INDEX_EDITS:
        if source.count(before) != 1:
            raise ValueError("Write index source anchor differs.")
        source = source.replace(before, after)
    return (source.replace("\n", "\r\n") if crlf else source).encode("utf-8")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--scratch-budget", action="store_true", help="add configurable idle upload pool cap")
    parser.add_argument("--write-index", action="store_true", help="index repeated GPU write declarations")
    args = parser.parse_args()
    root = args.checkout.resolve()
    try:
        if not (root / ".git").exists():
            raise ValueError("Use a separate Git checkout.")
        pending = {}
        for path in EXPECTED:
            target = root / path
            if target.resolve() != target or not target.is_file():
                raise ValueError(f"Invalid source path: {path}")
            data = patch_source(path, target.read_bytes())
            if args.scratch_budget and path == HOST:
                data = patch_scratch(data)
            if args.write_index and path == HOST:
                data = patch_write_index(data)
            pending[target] = data
        if args.apply:
            for target, data in pending.items():
                target.write_bytes(data)
            print("Candidate applied. Review the diff before building.")
        else:
            print("Source revision checks passed; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
