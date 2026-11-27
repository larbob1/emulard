"""Generate an unregistered test-only xasync.rs postimage; never edit the source."""
import argparse
import hashlib
from pathlib import Path

PINNED_BLOB = "068d75f2a8a50b7a4f0ec7a45e9c849c657bcde1"
MARKER = b"mod hle_pool_native_review"
FIXTURE = Path(__file__).resolve().parents[1] / "probes" / "hle_pool_native_tests.rs"


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def preview(source, fixture, expected=PINNED_BLOB):
    if git_blob(source) != expected:
        raise ValueError("xasync.rs is not the exact pinned postimage")
    if MARKER in source or fixture.count(MARKER) != 1:
        raise ValueError("test module marker missing, duplicate, or already present")
    if fixture.count(b"#[cfg(test)]") != 1:
        raise ValueError("expected exactly one test-only module")
    return source + b"\n" + fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = preview(args.source.read_bytes(), FIXTURE.read_bytes())
    # Exclusive creation: refuse input path, existing output, or existing symlink.
    with args.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
