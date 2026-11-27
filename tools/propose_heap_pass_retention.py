# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only heap cache ownership preview; never writes runtime source."""
import argparse
import difflib
from pathlib import Path

EDITS = (
    ("crates/victory-gpu/src/descriptor/host.rs", "pub(crate) struct HostHeap {", "// Cache metadata and shadow references belong to this heap, not a\n// process-wide table indexed by recyclable heap addresses.\npub(crate) type HeapPassRanges = std::collections::HashMap<u32, (std::sync::Arc<crate::shadow::Shadow>, u64, u64)>;\n\npub(crate) struct HostHeap {"),
    ("crates/victory-gpu/src/descriptor/host.rs", "    changed: Mutex<std::collections::HashSet<u32>>,", "    changed: Mutex<std::collections::HashSet<u32>>,\n    pub(crate) pass_ranges: Mutex<(u64, HeapPassRanges)>,"),
    ("crates/victory-gpu/src/descriptor/host.rs", "            changed: Mutex::default(),", "            changed: Mutex::default(),\n            pass_ranges: Mutex::default(),"),
    ("crates/victory-gpu/src/draw.rs", "        type Ranges = std::collections::HashMap<u32, (std::sync::Arc<crate::shadow::Shadow>, u64, u64)>;\n        static RANGES: std::sync::Mutex<Option<std::collections::HashMap<usize, (u64, Ranges)>>> =\n            std::sync::Mutex::new(None);\n        let mut kept = RANGES.lock().unwrap_or_else(|e| e.into_inner());\n        let (passes, ranges) = kept\n            .get_or_insert_with(Default::default)\n            .entry(std::ptr::from_ref(host) as usize)\n            .or_insert_with(|| (0, Ranges::new()));", "        let mut kept = host.pass_ranges.lock().unwrap_or_else(|e| e.into_inner());\n        let (passes, ranges) = &mut *kept;"),
)


def preview(sources):
    result = dict(sources)
    for path, old, new in EDITS:
        if result[path].count(old) != 1 or new in result[path]:
            raise ValueError("missing, duplicate or previously applied anchor: " + path)
        result[path] = result[path].replace(old, new, 1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    sources = {name: (args.prepared / name).read_text(encoding="utf-8")
               for name in dict.fromkeys(path for path, _, _ in EDITS)}
    result = preview(sources)
    for name in sources:
        print("".join(difflib.unified_diff(sources[name].splitlines(True),
              result[name].splitlines(True), "a/" + name, "b/" + name)), end="")


if __name__ == "__main__":
    main()
