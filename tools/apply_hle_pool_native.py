# SPDX-License-Identifier: GPL-3.0-or-later
"""Compose independently verified append-only previews from pristine HLE source."""
import argparse
from pathlib import Path
import preview_hle_pool_native as baseline
import test_hle_idle_suite_preview as retirement

BASELINE_FIXTURE_PIN = "0ad7572364eeb73af3cf77832805cc8798348c89"

def compose(source, reentrant, fixtures, expected=baseline.PINNED_BLOB):
    if baseline.git_blob(reentrant) != BASELINE_FIXTURE_PIN:
        raise ValueError("reentrant fixture identity mismatch")
    first = baseline.preview(source, reentrant, expected)
    second = retirement.preview(source, fixtures, expected)
    prefix = source + b"\n"
    if not first.startswith(prefix) or not second.startswith(prefix):
        raise ValueError("production prefix changed")
    combined = first + b"\n" + second[len(prefix):]
    markers = [baseline.MARKER] + [generator.MARKER for generator, _ in retirement.MODULES]
    if any(combined.count(marker) != 1 for marker in markers):
        raise ValueError("duplicate or missing module")
    return combined

def install(checkout):
    path = checkout / "crates/victory-hle/src/modules/xasync.rs"
    updated = compose(path.read_bytes(), baseline.FIXTURE.read_bytes(), retirement.fixtures())
    path.write_bytes(updated)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    install(parser.parse_args().checkout)
