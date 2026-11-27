# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline frozen AI0 review metadata checker. Never queries or changes GitHub.

Matching supplied metadata is not proof of authenticity, current state,
prepared-source compatibility, reviewer approval, or performance.
"""
import argparse
import json
from pathlib import Path

BASE = "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7"
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
# Frozen verified observations from individual push jobs, not merge jobs.
EXPECTED = json.loads(r'''[
 {
  "pr": 62,
  "head": "a2feaefde8732808c3e292c1128856c5f9cc80a2",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "docs/validation-readiness-review.md",
    "added",
    74,
    0
   ]
  ],
  "run": 46032924791,
  "synthetic_job": 140621001694,
  "synthetic_head": "a2feaefde8732808c3e292c1128856c5f9cc80a2",
  "synthetic_status": "success",
  "portable_job": 140621003735,
  "portable_status": "skipped",
  "python_passed": 113,
  "range_passed": 4,
  "group": "tooling"
 },
 {
  "pr": 63,
  "head": "211f74bb0893d866d60aca05c136588456ac049a",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "tools/ai0_source_overlap.py",
    "added",
    140,
    0
   ],
   [
    "tools/test_ai0_source_overlap.py",
    "added",
    113,
    0
   ]
  ],
  "run": 46033309116,
  "synthetic_job": 140622314289,
  "synthetic_head": "211f74bb0893d866d60aca05c136588456ac049a",
  "synthetic_status": "success",
  "portable_job": 140622316477,
  "portable_status": "skipped",
  "python_passed": 126,
  "range_passed": 4,
  "group": "tooling"
 },
 {
  "pr": 64,
  "head": "1b118a210d02d19686a9389fc30ea723c670bec4",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "probes/detile_last_run_review.rs",
    "added",
    60,
    0
   ],
   [
    "tools/preview_ai0_detile_run.py",
    "added",
    55,
    0
   ],
   [
    "tools/test_ai0_detile_run.py",
    "added",
    88,
    0
   ]
  ],
  "run": 46033728865,
  "synthetic_job": 140623740655,
  "synthetic_head": "1b118a210d02d19686a9389fc30ea723c670bec4",
  "synthetic_status": "success",
  "portable_job": 140623743511,
  "portable_status": "skipped",
  "python_passed": 117,
  "range_passed": 4,
  "group": "texture"
 },
 {
  "pr": 65,
  "head": "5af0fa2cbadf311947f0101eefad18b16bcc2f9a",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "probes/texture_spread_review.rs",
    "added",
    21,
    0
   ],
   [
    "tools/preview_ai0_spread_table.py",
    "added",
    40,
    0
   ],
   [
    "tools/test_ai0_spread_table.py",
    "added",
    238,
    0
   ]
  ],
  "run": 46034053268,
  "synthetic_job": 140624869712,
  "synthetic_head": "5af0fa2cbadf311947f0101eefad18b16bcc2f9a",
  "synthetic_status": "success",
  "portable_job": 140624872167,
  "portable_status": "skipped",
  "python_passed": 116,
  "range_passed": 4,
  "group": "texture"
 },
 {
  "pr": 66,
  "head": "3b22fabc99cef39f20b87abe67e8e4e1a9c0e6c1",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "probes/rect_copy_review.rs",
    "added",
    29,
    0
   ],
   [
    "tools/preview_ai0_rect_copy.py",
    "added",
    49,
    0
   ],
   [
    "tools/test_ai0_rect_copy.py",
    "added",
    86,
    0
   ]
  ],
  "run": 46034357407,
  "synthetic_job": 140625879108,
  "synthetic_head": "3b22fabc99cef39f20b87abe67e8e4e1a9c0e6c1",
  "synthetic_status": "success",
  "portable_job": 140625883913,
  "portable_status": "skipped",
  "python_passed": 116,
  "range_passed": 4,
  "group": "primitive"
 },
 {
  "pr": 67,
  "head": "2d97a632ce340e84e8bb04b26aaab211b8dd6e3b",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "tools/preview_ai0_rect_slot_mask.py",
    "added",
    47,
    0
   ],
   [
    "tools/test_ai0_rect_slot_mask.py",
    "added",
    129,
    0
   ]
  ],
  "run": 46034853680,
  "synthetic_job": 140627556139,
  "synthetic_head": "2d97a632ce340e84e8bb04b26aaab211b8dd6e3b",
  "synthetic_status": "success",
  "portable_job": 140627559252,
  "portable_status": "skipped",
  "python_passed": 116,
  "range_passed": 4,
  "group": "draw"
 },
 {
  "pr": 68,
  "head": "ff250700594da5e4838cce95bb5a9b147d8a0c66",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "tools/ai0_full_module_parity.py",
    "added",
    179,
    0
   ],
   [
    "tools/test_ai0_full_module_parity.py",
    "added",
    66,
    0
   ]
  ],
  "run": 46035428750,
  "synthetic_job": 140629502767,
  "synthetic_head": "ff250700594da5e4838cce95bb5a9b147d8a0c66",
  "synthetic_status": "success",
  "portable_job": 140629505991,
  "portable_status": "skipped",
  "python_passed": 118,
  "range_passed": 4,
  "group": "tooling"
 },
 {
  "pr": 69,
  "head": "24ae553e449bac498f29cde7395d6b6ef95ec888",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "tools/preview_ai0_fresh_slot_set.py",
    "added",
    46,
    0
   ],
   [
    "tools/test_ai0_fresh_slot_set.py",
    "added",
    142,
    0
   ]
  ],
  "run": 46036681453,
  "synthetic_job": 140633734659,
  "synthetic_head": "24ae553e449bac498f29cde7395d6b6ef95ec888",
  "synthetic_status": "success",
  "portable_job": 140633736487,
  "portable_status": "skipped",
  "python_passed": 116,
  "range_passed": 4,
  "group": "draw"
 },
 {
  "pr": 70,
  "head": "1710d374f7d6c22b6ef158f2704fb0b5653ea91c",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "tools/preview_ai0_root_constant_buffer.py",
    "added",
    46,
    0
   ],
   [
    "tools/test_ai0_root_constant_buffer.py",
    "added",
    142,
    0
   ]
  ],
  "run": 46037269822,
  "synthetic_job": 140635733748,
  "synthetic_head": "1710d374f7d6c22b6ef158f2704fb0b5653ea91c",
  "synthetic_status": "success",
  "portable_job": 140635736330,
  "portable_status": "skipped",
  "python_passed": 116,
  "range_passed": 4,
  "group": "draw"
 },
 {
  "pr": 71,
  "head": "036dec4dc4b6a012d2e860e1ae779b67f75719eb",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "tools/preview_ai0_ready_copy_prefix.py",
    "added",
    43,
    0
   ],
   [
    "tools/test_ai0_ready_copy_prefix.py",
    "added",
    152,
    0
   ]
  ],
  "run": 46037787255,
  "synthetic_job": 140637490293,
  "synthetic_head": "036dec4dc4b6a012d2e860e1ae779b67f75719eb",
  "synthetic_status": "success",
  "portable_job": 140637492164,
  "portable_status": "skipped",
  "python_passed": 116,
  "range_passed": 4,
  "group": "memory"
 },
 {
  "pr": 72,
  "head": "4a44d7bfec6aaf7a9acb3643882addb8203ddeec",
  "base": "bbea12cb0b2b29618bf4e410d272fe97b81f4bf7",
  "ahead": 1,
  "behind": 0,
  "state": "open",
  "draft": true,
  "files": [
   [
    "tools/preview_ai0_copy_identity_index.py",
    "added",
    65,
    0
   ],
   [
    "tools/test_ai0_copy_identity_index.py",
    "added",
    132,
    0
   ]
  ],
  "run": 46038099830,
  "synthetic_job": 140638573817,
  "synthetic_head": "4a44d7bfec6aaf7a9acb3643882addb8203ddeec",
  "synthetic_status": "success",
  "portable_job": 140638576285,
  "portable_status": "skipped",
  "python_passed": 116,
  "range_passed": 4,
  "group": "memory"
 }
]''')


def canonical(row):
    if not isinstance(row, dict):
        raise ValueError("row is not an object")
    if set(row) != set(EXPECTED[0]):
        raise ValueError("unexpected or missing row keys")
    # JSON equality distinguishes bools from ints, unlike Python equality.
    result = dict(row)
    files = result["files"]
    if not isinstance(files, list) or any(
        not isinstance(f, list) or len(f) != 4 or not isinstance(f[0], str)
        for f in files
    ):
        raise ValueError("invalid files list")
    result["files"] = sorted(files, key=lambda f: f[0])
    return json.dumps(result, sort_keys=True, separators=(",", ":"))


def verify(rows):
    if not isinstance(rows, list) or len(rows) != len(EXPECTED):
        raise ValueError("incomplete or extra proposal rows")
    expected = {r["pr"]: canonical(r) for r in EXPECTED}
    seen = set()
    paths = set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get("pr")) is not int:
            raise ValueError("invalid PR identity")
        pr = row["pr"]
        if pr not in expected or pr in seen:
            raise ValueError("unexpected or duplicate PR identity")
        seen.add(pr)
        if canonical(row) != expected[pr]:
            raise ValueError("frozen metadata drift for PR " + str(pr))
        for f in row["files"]:
            if f[0] in paths:
                raise ValueError("shared repository path")
            paths.add(f[0])
    return {
        "matched_proposals": len(seen),
        "distinct_repository_paths": len(paths),
        "added_lines": sum(f[2] for row in rows for f in row["files"]),
        "shared_upstream_groups": {
            group: sorted(row["pr"] for row in rows if row["group"] == group)
            for group in ("texture", "draw", "memory")
        },
        "independent_review": "REQUIRED",
        "native_runtime_evidence": "NOT_ESTABLISHED",
        "performance_evidence": "NOT_ESTABLISHED",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("snapshot", type=Path, nargs="?")
    p.add_argument("--print-reference", action="store_true")
    a = p.parse_args(argv)
    if a.print_reference:
        if a.snapshot is not None:
            p.error("choose reference or snapshot validation")
        print(json.dumps(EXPECTED, indent=2))
        return 0
    if a.snapshot is None:
        p.error("supply independently collected metadata")
    try:
        if a.snapshot.stat().st_size > 1024 * 1024:
            raise ValueError("snapshot exceeds size limit")
        result = verify(json.loads(a.snapshot.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        print("INVALID: snapshot is incomplete, changed, or malformed")
        return 1
    print(json.dumps(result, indent=2))
    print("Frozen metadata match only; no approval or live authenticity proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
