# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only identity index for append-only raw-address copies."""
import argparse
import hashlib
from pathlib import Path

PIN = "c25636783511fdfbf9692fdd36ef150f69ea666e"
STRUCT = "struct Memory {"
STRUCT_END = "\n}\n\n// SAFETY: the mappings"
IMPL = "impl Memory {"
IMPL_END = "\n}\n\n/// Before a draw"
OLD = "        let n = match self.copies.iter().position(|c| Arc::ptr_eq(c, &shadow)) {\n            Some(n) => n,\n            None if self.copies.len() < COPIES as usize => {\n                self.copies.push(shadow.clone());\n                let n = self.copies.len() - 1;\n"
NEW = "        let identity = Arc::as_ptr(&shadow) as usize;\n        let n = match self.copy_index.get(&identity).copied() {\n            Some(n) => n,\n            None if self.copies.len() < COPIES as usize => {\n                self.copies.push(shadow.clone());\n                let n = self.copies.len() - 1;\n                self.copy_index.insert(identity, n);\n"
FIELD = "    copies: Vec<Arc<Shadow>>,\n"
INIT = "            copies: Vec::new(),\n"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("identity index anchor mismatch")
    return source.replace(old, new, 1)


def clone(source):
    for marker in (STRUCT, STRUCT_END, IMPL, IMPL_END):
        if source.count(marker) != 1:
            raise ValueError("memory struct/impl boundary mismatch")
    if "MemoryIndexed" in source or "copy_index" in source:
        raise ValueError("prior candidate present")
    a = source.index(STRUCT)
    b = source.index(STRUCT_END, a) + 2
    c = source.index(IMPL, b)
    d = source.index(IMPL_END, c) + 2
    struct = replace_once(source[a:b], STRUCT, "struct MemoryIndexed {")
    struct = replace_once(struct, FIELD, FIELD + "    copy_index: HashMap<usize, usize>,\n")
    methods = replace_once(source[c:d], IMPL, "impl MemoryIndexed {")
    methods = replace_once(methods, "fn new() -> Option<Memory>", "fn new() -> Option<MemoryIndexed>")
    methods = replace_once(methods, "Some(Memory {", "Some(MemoryIndexed {")
    methods = replace_once(methods, INIT, INIT + "            copy_index: HashMap::new(),\n")
    methods = replace_once(methods, OLD, NEW)
    return "#[cfg(test)]\n" + struct + "\n\n#[cfg(test)]\n" + methods + "\n"


def preview(source, expected=PIN):
    if blob(source) != expected:
        raise ValueError("memory source blob mismatch")
    return source + b"\n" + clone(source.decode()).encode()


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
