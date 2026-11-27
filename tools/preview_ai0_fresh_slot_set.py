# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only descriptor fresh-slot set preview, not runtime registration."""
import argparse
import hashlib
from pathlib import Path

PIN = "41380c23a61b93000c4886265c3063676ddc4864"
START = "    pub(crate) fn tables(\n"
END = "\n    }\n\n    /// The first draws"
OLD = "        let tables = |u: &&UsedResource| u.root == RootType::Table;\n        let mut fresh: Vec<u8> = used\n            .iter()\n            .filter(tables)\n            .filter(|u| u.kind == ResourceType::Cbv)\n            .map(|u| u.slot)\n            .collect();\n        // Tables reaching past a host heap smaller than the title's (the\n        // host's limit, 1,000,000 views on NVIDIA) are made afresh too: the\n        // title's slots there have no host slot of their own.\n        for u in used.iter().filter(tables) {\n            if fresh.contains(&u.slot) {\n                continue;\n            }\n            let Some(&Root::Table(table)) = self.roots_ref(compute).get(usize::from(u.slot)) else {\n                continue;\n            };\n            let end = table + u64::from(u.table_offset_dwords) * 4;\n            let Some(heap) = self.heap_of(table) else {\n                continue;\n            };\n            let (Some(host), Some(index)) = (heap.host(), heap.index(end)) else {\n                continue;\n            };\n            if index >= host.count() {\n                fresh.push(u.slot);\n            }\n        }\n        fresh.sort_unstable();\n        fresh.dedup();\n        for u in used.iter().filter(tables) {\n            if !fresh.contains(&u.slot) {\n                self.table_entry(list, u, compute);\n            }\n        }\n        let mut made = Vec::new();\n        for slot in fresh {\n"
NEW = "        let tables = |u: &&UsedResource| u.root == RootType::Table;\n        let mut fresh = [0u64; 4];\n        let contains = |mask: &[u64; 4], slot: u8| {\n            mask[usize::from(slot) / 64] & (1u64 << (slot % 64)) != 0\n        };\n        let insert = |mask: &mut [u64; 4], slot: u8| {\n            mask[usize::from(slot) / 64] |= 1u64 << (slot % 64);\n        };\n        for u in used.iter().filter(tables).filter(|u| u.kind == ResourceType::Cbv) {\n            insert(&mut fresh, u.slot);\n        }\n        // Tables reaching past a host heap smaller than the title's (the\n        // host's limit, 1,000,000 views on NVIDIA) are made afresh too: the\n        // title's slots there have no host slot of their own.\n        for u in used.iter().filter(tables) {\n            if contains(&fresh, u.slot) {\n                continue;\n            }\n            let Some(&Root::Table(table)) = self.roots_ref(compute).get(usize::from(u.slot)) else {\n                continue;\n            };\n            let end = table + u64::from(u.table_offset_dwords) * 4;\n            let Some(heap) = self.heap_of(table) else {\n                continue;\n            };\n            let (Some(host), Some(index)) = (heap.host(), heap.index(end)) else {\n                continue;\n            };\n            if index >= host.count() {\n                insert(&mut fresh, u.slot);\n            }\n        }\n        for u in used.iter().filter(tables) {\n            if !contains(&fresh, u.slot) {\n                self.table_entry(list, u, compute);\n            }\n        }\n        let mut made = Vec::new();\n        let slots = fresh.into_iter().enumerate().flat_map(|(word, mut bits)| {\n            std::iter::from_fn(move || {\n                if bits == 0 {\n                    return None;\n                }\n                let bit = bits.trailing_zeros();\n                bits &= bits - 1;\n                Some((word * 64 + bit as usize) as u8)\n            })\n        });\n        for slot in slots {\n"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def clone(source):
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("tables method boundaries mismatch")
    a = source.index(START)
    b = source.index(END, a) + len("\n    }")
    original = source[a:b]
    if original.count(OLD) != 1 or "tables_fresh_mask" in source:
        raise ValueError("fresh classification anchor or prior candidate mismatch")
    return original.replace(START, "    fn tables_fresh_mask(\n", 1).replace(OLD, NEW, 1)


def preview(source, expected=PIN):
    if blob(source) != expected:
        raise ValueError("draw source blob mismatch")
    return source + b"\n#[cfg(test)]\nimpl State {\n" + clone(source.decode()).encode() + b"\n}\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    data = preview(a.source.read_bytes())
    with a.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
