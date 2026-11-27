#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Port reverse-alias BTreeSet indexing from fxceless to paired-wave."""
import argparse
from pathlib import Path

PATCHES = {
    "crates/victory-hle/src/modules/xmem.rs": (
        ("use std::collections::{BTreeMap, HashMap};",
         "use std::collections::{BTreeMap, BTreeSet, HashMap};"),
        ("    shown: HashMap<(usize, usize), Vec<usize>>,",
         "    shown: HashMap<(usize, usize), BTreeSet<usize>>,"),
        ("physical.shown.entry(slice.key(k)).or_default().push(base + k * PAGE);",
         "physical.shown.entry(slice.key(k)).or_default().insert(base + k * PAGE);"),
        ("addresses.retain(|&a| a != at + k * PAGE);",
         "addresses.remove(&(at + k * PAGE));"),
    ),
    "crates/victory-gpu/src/inplace.rs": (
        ("use std::collections::BTreeMap;",
         "use std::collections::{BTreeMap, BTreeSet};"),
        ("    pages: BTreeMap<(usize, u64), Vec<usize>>,",
         "    pages: BTreeMap<(usize, u64), BTreeSet<usize>>,"),
        ("v.pages.entry((section, offset + (k * K64) as u64)).or_default().push(at + k * K64);",
         "v.pages.entry((section, offset + (k * K64) as u64)).or_default().insert(at + k * K64);"),
        ("pages.retain(|&shown| shown != page);",
         "pages.remove(&page);"),
        ("    v.pages.get(&(section, offset + within as u64)).cloned().unwrap_or_default()",
         "    v.pages.get(&(section, offset + within as u64)).map(|pages| pages.iter().copied().collect()).unwrap_or_default()"),
        ("        let shown = v.pages.get(&(section, offset - offset % K64 as u64))?.clone();\n        if shown.len() > crate::watch::MANY_VIEWS {\n            return None;\n        }",
         "        let shown = v.pages.get(&(section, offset - offset % K64 as u64))?;\n        if shown.len() > crate::watch::MANY_VIEWS {\n            return None;\n        }\n        let shown: Vec<_> = shown.iter().copied().collect();"),
        ("    /// Only private memory committed whole, read-write, is taken for a part.",
         "    /// Reverse aliases are unique, and removing a view preserves others.\n    #[test]\n    fn reverse_alias_index_preserves_other_views() {\n        let at = 0x7_8000_0000usize;\n        let other = at + 4 * K64;\n        let third = at + 8 * K64;\n        let section = 0x7f012345usize;\n        title_memory_view(other, K64, section, 0);\n        title_memory_view(at, K64, section, 0);\n        title_memory_view(third, K64, section, K64 as u64);\n        let mut aliases = pages_of(at);\n        aliases.sort_unstable();\n        assert_eq!(aliases, vec![at, other]);\n        assert_eq!(pages_of(third), vec![third]);\n        views_gone(other, K64);\n        assert_eq!(pages_of(at), vec![at]);\n        assert!(pages_of(other).is_empty());\n        assert_eq!(pages_of(third), vec![third]);\n        views_gone(at, K64);\n        views_gone(third, K64);\n        assert!(pages_of(at).is_empty());\n    }\n\n    /// Only private memory committed whole, read-write, is taken for a part."),
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
        parser.exit(1, f"Alias index preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
