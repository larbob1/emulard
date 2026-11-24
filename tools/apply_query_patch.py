#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply a revision-pinned query-result range validation candidate."""
import argparse
from pathlib import Path
import sys

from apply_memory_patch import blob_hash

SOURCE = "crates/victory-gpu/src/list.rs"
EXPECTED = "8ce9856899db63109b27ce1017113b665499a20c"
BEFORE = "    if offset + u64::from(count) * bytes > size {\n        return;\n    }"
AFTER = "    if !query_result_fits(offset, count, bytes, size) {\n        return;\n    }"
ANCHOR = "/// `ResolveQueryData(heap, type, first, count, buffer, offset)`: writes"
HELPER = "/// Validate the entire query result range before computing any pointer.\nfn query_result_fits(offset: u64, count: u32, stride: u64, size: u64) -> bool {\n    u64::from(count)\n        .checked_mul(stride)\n        .and_then(|bytes| offset.checked_add(bytes))\n        .is_some_and(|end| end <= size)\n}\n\n#[cfg(test)]\nmod query_range_tests {\n    use super::query_result_fits;\n\n    #[test]\n    fn exact_end_and_out_of_bounds() {\n        assert!(query_result_fits(16, 2, 8, 32));\n        assert!(!query_result_fits(16, 2, 8, 31));\n        assert!(query_result_fits(32, 0, 8, 32));\n        assert!(!query_result_fits(33, 0, 8, 32));\n    }\n\n    #[test]\n    fn addition_and_multiplication_overflow() {\n        assert!(!query_result_fits(u64::MAX - 3, 1, 8, u64::MAX));\n        assert!(!query_result_fits(0, 2, u64::MAX, u64::MAX));\n        assert!(query_result_fits(u64::MAX - 8, 1, 8, u64::MAX));\n    }\n\n    #[test]\n    fn statistics_stride() {\n        assert!(query_result_fits(8, 2, 88, 184));\n        assert!(!query_result_fits(8, 2, 88, 183));\n    }\n}\n\n"

def patch_source(data):
    normalized = data.replace(b"\r\n", b"\n")
    if blob_hash(normalized) != EXPECTED:
        raise ValueError("Query source revision differs from the reviewed blob.")
    source = normalized.decode("utf-8")
    if source.count(BEFORE) != 1 or source.count(ANCHOR) != 1:
        raise ValueError("Query source anchors differ.")
    result = source.replace(BEFORE, AFTER).replace(ANCHOR, HELPER + ANCHOR)
    updated = result.encode("utf-8")
    return updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkout", type=Path)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    root = args.checkout.resolve()
    try:
        target = root / SOURCE
        if not (root / ".git").exists() or target.resolve() != target or not target.is_file():
            raise ValueError("A separate, valid Git checkout is required.")
        updated = patch_source(target.read_bytes())
        if args.apply:
            target.write_bytes(updated)
            print("Query candidate applied.")
        else:
            print("Query source validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
