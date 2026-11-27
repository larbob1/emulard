# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only raw-address ready prefix skip; not registered in runtime."""
import argparse
import hashlib
from pathlib import Path

PIN = "c25636783511fdfbf9692fdd36ef150f69ea666e"
START = "pub(crate) fn ready(\n"
OLD = "    const READ: usize = usize::MAX - 0x6d;\n    const WRITE: usize = usize::MAX - 0x6e;\n    let first_read = list.first_use(READ);\n    let first_write = writes && list.first_use(WRITE);\n    for (n, shadow) in m.copies.iter().enumerate() {\n        let (start, len) = shadow.span();\n        if first_read || n >= numbered {\n            shadow.refresh(list, start, len);\n        }\n        if writes && (first_write || n >= numbered) {\n            shadow.gpu_writes(list, start, len);\n        }\n    }\n    if first_read {\n        list.keep(&m.directory.0);\n        list.keep(&m.faults.0);\n    }\n"
NEW = "    const READ: usize = usize::MAX - 0x6d;\n    const WRITE: usize = usize::MAX - 0x6e;\n    let first_read = list.first_use(READ);\n    let first_write = writes && list.first_use(WRITE);\n    // Earlier copies need no work once this list has registered both\n    // applicable uses. Retain their original indices for the predicates.\n    let begin = if first_read || first_write { 0 } else { numbered };\n    for (n, shadow) in m.copies.iter().enumerate().skip(begin) {\n        let (start, len) = shadow.span();\n        if first_read || n >= numbered {\n            shadow.refresh(list, start, len);\n        }\n        if writes && (first_write || n >= numbered) {\n            shadow.gpu_writes(list, start, len);\n        }\n    }\n    if first_read {\n        list.keep(&m.directory.0);\n        list.keep(&m.faults.0);\n    }\n"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def clone(source):
    if source.count(START) != 1 or source.count(OLD) != 1 or "ready_skip_prefix" in source:
        raise ValueError("ready function or loop anchor mismatch")
    method = source[source.index(START):]
    if not method.endswith("}\n") or method.count(OLD) != 1:
        raise ValueError("ready function end mismatch")
    return method.replace(START, "fn ready_skip_prefix(\n", 1).replace(OLD, NEW, 1)


def preview(source, expected=PIN):
    if blob(source) != expected:
        raise ValueError("memory source blob mismatch")
    return source + b"\n#[cfg(test)]\n" + clone(source.decode()).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    a = parser.parse_args()
    data = preview(a.source.read_bytes())
    with a.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
