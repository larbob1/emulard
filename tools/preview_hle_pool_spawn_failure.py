"""Preview only: exact pinned xasync.rs with a test-only spawn panic hook."""
import argparse
from pathlib import Path

from preview_hle_pool_native import PINNED_BLOB, git_blob

FIXTURE = Path(__file__).resolve().parents[1] / "probes" / "hle_pool_spawn_failure_native.rs"
ANCHOR = b"            std::thread::spawn(move || self.work());"
REPLACEMENT = b"""            #[cfg(test)]
            hle_pool_spawn_failure_review::before_spawn();
            std::thread::spawn(move || self.work());"""
MARKER = b"mod hle_pool_spawn_failure_review"


def preview(source, fixture, expected=PINNED_BLOB):
    if git_blob(source) != expected:
        raise ValueError("not exact pinned xasync.rs")
    if source.count(ANCHOR) != 1:
        raise ValueError("expected unique Pool::submit spawn anchor")
    if MARKER in source or fixture.count(MARKER) != 1 or fixture.count(b"#[cfg(test)]") != 1:
        raise ValueError("expected one new test-only module")
    return source.replace(ANCHOR, REPLACEMENT, 1) + b"\n" + fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = preview(args.source.read_bytes(), FIXTURE.read_bytes())
    with args.output.open("xb") as out:
        out.write(result)


if __name__ == "__main__":
    main()
