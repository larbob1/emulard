#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert a local page mapping trace into a bounded replay with synthetic data."""

import argparse
from collections import Counter
import csv
from pathlib import Path

PAGE = 64 * 1024
WINDOW = 128
MAX_OPERATIONS = 32_768
MAX_SOURCE_PAGES = 4_096


def read_ranges(path):
    with path.open(newline="") as stream:
        for row in csv.reader(stream):
            frame, address, pool, pool_pages, kind, start, count = map(int, row)
            if address % PAGE or pool % PAGE or min(frame, address, pool, pool_pages, start, count) < 0:
                raise ValueError("invalid page range")
            if kind not in (0, 1, 2, 3):
                raise ValueError(f"unknown mapping kind {kind}")
            if (kind == 0 and start + count > pool_pages) or (kind == 1 and start >= pool_pages):
                raise ValueError("mapping refers past the end of a pool")
            if count and kind != 3:
                yield frame, address // PAGE, pool // PAGE, kind, start, count


def normalize(rows, frame):
    activity = Counter()
    for at, dest, _, _, _, count in rows:
        if at == frame:
            for block in range(dest // WINDOW, (dest + count - 1) // WINDOW + 1):
                lo = max(dest, block * WINDOW)
                hi = min(dest + count, (block + 1) * WINDOW)
                activity[block] += hi - lo
    if not activity:
        raise ValueError(f"frame {frame} contains no mapping changes")
    base = activity.most_common(1)[0][0] * WINDOW
    sources = {}
    operations = []
    for at, dest, pool, kind, start, count in rows:
        if at > frame:
            continue
        for position in range(max(dest, base), min(dest + count, base + WINDOW)):
            if kind == 2:
                source = "-"
            else:
                page = pool + start + (position - dest if kind == 0 else 0)
                source = sources.setdefault(page, len(sources))
                if len(sources) > MAX_SOURCE_PAGES:
                    raise ValueError("replay exceeds the source page limit")
            operations.append(f"{position - base},{source}")
            if len(operations) > MAX_OPERATIONS:
                raise ValueError("replay exceeds the operation limit")
    if not sources:
        raise ValueError("the selected window has no source pages")
    return len(sources), operations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--frame", required=True, type=int, help="frame number in the capture")
    args = parser.parse_args()
    try:
        pages, operations = normalize(list(read_ranges(args.trace)), args.frame)
        args.output.write_text(
            f"{pages},{WINDOW}\n" + "\n".join(operations) + "\n", encoding="ascii"
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Frame {args.frame}: {len(operations)} operations, {pages} source pages.")


if __name__ == "__main__":
    main()
