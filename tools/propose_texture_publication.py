#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Review only: preview a guarded publication fix on the prepared runtime."""
import argparse
import difflib
from pathlib import Path

PATH = Path("crates/victory-gpu/src/texture.rs")
OLD = """                // A remap started after the snapshot was captured.
                // Do not publish this candidate; force a future refresh.
                if crate::watch::mapping_epoch() != epoch {
                    last.asked = 0;
                    snapshot_counts(size, copy_us, work_started.elapsed().as_micros() as u64, true);
                    return size;
                }"""
NEW = """                // Reacquire without waiting: an epoch comparison alone
                // does not exclude remapping during staging publication.
                let Some(publication) = crate::watch::title_memory_reading_now() else {
                    last.asked = 0;
                    snapshot_counts(size, copy_us, work_started.elapsed().as_micros() as u64, true);
                    return size;
                };
                if crate::watch::mapping_epoch() != epoch {
                    drop(publication);
                    last.asked = 0;
                    snapshot_counts(size, copy_us, work_started.elapsed().as_micros() as u64, true);
                    return size;
                }"""
OLD_END = """                // A remap during detile cannot invalidate the owned bytes,
                // but this snapshot may now be old. Retry rather than
                // treating it as the latest generation on the next check.
                let retry = crate::watch::mapping_epoch() != epoch;
                if retry {
                    last.asked = 0;
                    last.hash = None;
                }
                snapshot_counts(size, copy_us, work_started.elapsed().as_micros() as u64, retry);"""
NEW_END = """                // Retain the mapping guard through hash and staging
                // publication. Release before diagnostic logging.
                drop(publication);
                snapshot_counts(size, copy_us, work_started.elapsed().as_micros() as u64, false);"""

def preview(source):
    for old, new in ((OLD, NEW), (OLD_END, NEW_END)):
        if source.count(old) != 1:
            raise ValueError("missing or ambiguous texture publication anchor")
        source = source.replace(old, new, 1)
    return source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    path = args.prepared / PATH
    source = path.read_text(encoding="utf-8")
    changed = preview(source)
    print("".join(difflib.unified_diff(source.splitlines(True),
        changed.splitlines(True), "a/" + str(PATH), "b/" + str(PATH))), end="")

if __name__ == "__main__":
    main()
