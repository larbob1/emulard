"""Compose four pinned HLE test-only previews; never edit the input."""
import argparse
from pathlib import Path
import preview_hle_pool_native as api
import preview_hle_pool_gated_native as gated
import preview_hle_pool_spawn_failure as failure
import preview_hle_delayed_native as delayed

MODULES = (api, gated, failure, delayed)
BLOBS = (
    "0ad7572364eeb73af3cf77832805cc8798348c89",
    "4abbd4cde669ccca412814fba58598a013e4034e",
    "65f2f845c320d8060f02804ec88a4ec529ff8c3f",
    "5d3cc716a015526dfaa805b5894dfc96f7c45b07",
)
SPAWN = gated.ANCHOR
# The failure hook precedes spawn, the startup gate is inside its closure.
COMPOSED = failure.REPLACEMENT.replace(SPAWN, gated.REPLACEMENT, 1)
TESTS = (
    "hle_pool_native_review::reentrant_pool_callback_progress",
    "hle_pool_gated_native_review::pending_start_and_idle_notification",
    "hle_pool_spawn_failure_review::spawn_panic_preserves_queued_work",
    "hle_delayed_native_review::delayed_queue_lifetime_and_termination",
)


def load_fixtures():
    return tuple(module.FIXTURE.read_bytes() for module in MODULES)


def preview(source, fixtures, expected=api.PINNED_BLOB):
    if api.git_blob(source) != expected:
        raise ValueError("not exact pinned xasync.rs")
    if len(fixtures) != len(MODULES):
        raise ValueError("expected four pinned fixtures")
    if (failure.ANCHOR != SPAWN or failure.REPLACEMENT.count(SPAWN) != 1
            or source.count(SPAWN) != 1 or source.count(delayed.ANCHOR) != 1):
        raise ValueError("expected unique independent anchors")
    # Independently validate the existing preview contracts, before composing.
    for module, fixture, digest in zip(MODULES, fixtures, BLOBS):
        if api.git_blob(fixture) != digest:
            raise ValueError("fixture digest mismatch: " + module.FIXTURE.name)
        module.preview(source, fixture, expected)
    prefix = source.replace(SPAWN, COMPOSED, 1).replace(
        delayed.ANCHOR, delayed.REPLACEMENT, 1)
    if (prefix.count(COMPOSED) != 1 or prefix.count(delayed.REPLACEMENT) != 1
            or prefix.replace(COMPOSED, SPAWN, 1).replace(
                delayed.REPLACEMENT, delayed.ANCHOR, 1) != source):
        raise ValueError("composition is not reversible")
    result = prefix + b"".join(b"\n" + fixture for fixture in fixtures)
    if any(result.count(module.MARKER) != 1 for module in MODULES):
        raise ValueError("duplicate module marker")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = preview(args.source.read_bytes(), load_fixtures())
    with args.output.open("xb") as out:
        out.write(result)
    print("HLE native suite preview: four pinned test modules, source unchanged")
    for test in TESTS:
        print(test)


if __name__ == "__main__":
    main()
