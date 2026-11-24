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
TRACKER = "#[derive(Default)]\nstruct RawCopyProgress {\n    read_count: Option<usize>,\n    write_count: usize,\n}\n\nimpl RawCopyProgress {\n    fn schedule(&mut self, count: usize, writes: bool) -> (usize, usize, bool) {\n        let first = self.read_count.is_none();\n        let read_from = self.read_count.unwrap_or(0);\n        self.read_count = Some(count);\n        let write_from = if writes {\n            let previous = self.write_count;\n            self.write_count = count;\n            previous\n        } else {\n            count\n        };\n        (read_from, write_from, first)\n    }\n}\n\n#[cfg(test)]\nmod raw_copy_progress_tests {\n    use super::RawCopyProgress;\n\n    #[test]\n    fn interleaved_lists() {\n        let mut a = RawCopyProgress::default();\n        let mut b = RawCopyProgress::default();\n        assert_eq!(a.schedule(2, true), (0, 0, true));\n        assert_eq!(b.schedule(3, true), (0, 0, true));\n        assert_eq!(a.schedule(3, true), (2, 2, false));\n        assert_eq!(a.schedule(3, true), (3, 3, false));\n    }\n\n    #[test]\n    fn read_only_then_write() {\n        let mut a = RawCopyProgress::default();\n        assert_eq!(a.schedule(2, false), (0, 2, true));\n        assert_eq!(a.schedule(4, true), (2, 0, false));\n        assert_eq!(a.schedule(5, false), (4, 5, false));\n        assert_eq!(a.schedule(5, true), (5, 4, false));\n    }\n\n    #[test]\n    fn empty_then_reset() {\n        let mut a = RawCopyProgress::default();\n        assert_eq!(a.schedule(0, false), (0, 0, true));\n        assert_eq!(a.schedule(0, false), (0, 0, false));\n        assert_eq!(a.schedule(1, true), (0, 0, false));\n        a = RawCopyProgress::default();\n        assert_eq!(a.schedule(1, true), (0, 0, true));\n    }\n}\n\n"
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
    else:
        lines[292:309] = [SCHEDULE]
        del lines[259]
    updated = "".join(lines).encode("utf-8")
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
        for path in EXPECTED:
            target = root / path
            if target.resolve() != target or not target.is_file():
                raise ValueError(f"Invalid source path: {path}")
            pending[target] = patch_source(path, target.read_bytes())
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
