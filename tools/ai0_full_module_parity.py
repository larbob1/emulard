# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone full-module validation for the exact AI0 #64/#65/#66 drafts.

Supply the two pinned Rust source files and three separate proposal checkouts.
No networking, no title data, no production changes. Run in an isolated
developer/CI environment, never on the owner's machine as AI0.
This checks raw modules, not a complete prepared runtime or GPU behavior.
"""
import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
TEXTURE_PIN = "fa719c93953d9e6589c4d2cd27a13d773863c316"
PRIMITIVE_PIN = "3f73ee71ec98b59472be17fbf48f9198424fcb74"
TEXTURE_TESTS = frozenset("tests::" + name for name in (
    "extents_past_the_hardware_limit_are_invalid",
    "blocks_hold_their_size_in_elements",
    "addresses_are_a_bijection_and_copies_round_trip",
    "tiled_chunks_match_element_offsets_with_odd_row_pitches",
    "hand_checked_addresses", "mip_tail_comes_first",
    "depth_stencil_is_two_planes", "texture_copies_reject_overflowing_pitches",
    "volume_copy_rejects_overflowing_depth_pitch",
    "bad_descriptions_and_buffers_are_refused",
))
PRIMITIVE_TESTS = frozenset("tests::" + name for name in (
    "rectangles_get_their_fourth_corner",
    "halves_round_up_into_the_next_power_of_two",
    "elements_past_the_stride_are_left_alone",
    "half_subnormals_convert_in_both_directions",
))


@dataclass(frozen=True)
class Case:
    label: str
    head: str
    source_pin: str
    script: str
    script_pin: str
    fixture: str
    fixture_pin: str
    candidate: str
    baseline: frozenset


CASES = (
    Case("pr64", "1b118a210d02d19686a9389fc30ea723c670bec4", TEXTURE_PIN,
         "tools/preview_ai0_detile_run.py", "a120dd694f4c57256b9ad585dbaceadd0df2d21b",
         "probes/detile_last_run_review.rs", "abda75b1334db1899a9ca76ee86559335c7bda34",
         "ai0_detile_last_run_review::actual_layout_copy_parity", TEXTURE_TESTS),
    Case("pr65", "5af0fa2cbadf311947f0101eefad18b16bcc2f9a", TEXTURE_PIN,
         "tools/preview_ai0_spread_table.py", "e0770142d98be9fe7fe76ca6f29530f4a958010e",
         "probes/texture_spread_review.rs", "6f0685a53b917ba75d47e295d3d2b71bb550b1dd",
         "ai0_texture_spread_review::actual_pattern_axis_table_parity", TEXTURE_TESTS),
    Case("pr66", "3b22fabc99cef39f20b87abe67e8e4e1a9c0e6c1", PRIMITIVE_PIN,
         "tools/preview_ai0_rect_copy.py", "86b4f8ef68424aedfe98403d69993e0f5aa1f6e6",
         "probes/rect_copy_review.rs", "001e8b74307545af3dbd63576bcb1a4bbb119c97",
         "ai0_rect_copy_review::actual_rectangle_expansion_parity", PRIMITIVE_TESTS),
)


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def pinned(path, expected):
    data = path.read_bytes()
    if blob(data) != expected:
        raise ValueError("pinned input blob mismatch")
    return data


def listing_ok(output, expected):
    lines = [line for line in output.splitlines() if line.strip()]
    if not expected or len(lines) != len(expected) + 1:
        return False
    names = [re.fullmatch(r"(\S+): test", line) for line in lines[:-1]]
    return (all(names) and {m.group(1) for m in names} == expected
            and re.fullmatch(rf"{len(expected)} tests?, 0 benchmarks?", lines[-1]) is not None)


def receipt_ok(output, expected):
    lines = [line for line in output.splitlines() if line.strip()]
    if not expected or len(lines) not in (len(expected) + 1, len(expected) + 2):
        return False
    if lines[0] == f"running {len(expected)} test" or lines[0] == f"running {len(expected)} tests":
        lines = lines[1:]
    if len(lines) != len(expected) + 1:
        return False
    names = [re.fullmatch(r"test (\S+) \.\.\. ok", line) for line in lines[:-1]]
    summary = (rf"test result: ok\. {len(expected)} passed; 0 failed; 0 ignored; "
               r"0 measured; 0 filtered out; finished in \d+(?:\.\d+)?s")
    return (all(names) and {m.group(1) for m in names} == expected
            and re.fullmatch(summary, lines[-1]) is not None)


def command(args, cwd, timeout):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        # Do not publish compiler output, source lines, or local paths.
        raise ValueError("preview/compiler/test subprocess failed")
    return result.stdout


def run_module(source, directory, rustc, expected):
    executable = directory / ("module-tests.exe" if sys.platform == "win32" else "module-tests")
    command([rustc, "--edition=2021", "--test", str(source), "-o", str(executable)],
            directory, 120)
    listed = command([str(executable), "--list"], directory, 30)
    if not listing_ok(listed, expected):
        raise ValueError("unexpected test discovery")
    output = command([str(executable), "--test-threads=1", "--format=pretty"], directory, 120)
    if not receipt_ok(output, expected):
        raise ValueError("incomplete or unexpected test receipt")
    return len(expected)


def run_case(case, source_path, checkout, rustc, directory):
    original = pinned(source_path, case.source_pin)
    script = pinned(checkout / case.script, case.script_pin)
    fixture = pinned(checkout / case.fixture, case.fixture_pin)
    for relative, data in ((case.script, script), (case.fixture, fixture)):
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    source = directory / "original.rs"
    source.write_bytes(original)
    output = directory / "preview.rs"
    command([sys.executable, "-I", str(directory / case.script), str(source), str(output)],
            directory, 30)
    generated = output.read_bytes()
    if source.read_bytes() != original or not generated.startswith(original) or generated == original:
        raise ValueError("preview did not preserve original bytes")
    expected = case.baseline | {case.candidate}
    count = run_module(output, directory, rustc, expected)
    return count, blob(generated)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--texture", type=Path, required=True)
    p.add_argument("--primitive", type=Path, required=True)
    for case in CASES:
        p.add_argument("--" + case.label, type=Path, required=True)
    a = p.parse_args(argv)
    rustc = shutil.which("rustc")
    if rustc is None:
        print("INVALID: Rust compiler unavailable")
        return 2
    # Refuse an incorrect source/proposal before any compilation or preview.
    try:
        for case in CASES:
            path = a.texture if case.source_pin == TEXTURE_PIN else a.primitive
            pinned(path, case.source_pin)
            checkout = getattr(a, case.label)
            pinned(checkout / case.script, case.script_pin)
            pinned(checkout / case.fixture, case.fixture_pin)
    except (OSError, ValueError):
        print("INVALID: source/proposal identity could not be verified")
        return 2
    try:
        compiler = command([rustc, "-vV"], Path.cwd(), 30)
        host = re.findall(r"^host: (\S+)$", compiler, re.M)
        release = re.findall(r"^release: (\S+)$", compiler, re.M)
        if len(host) != 1 or len(release) != 1:
            raise ValueError("compiler identity missing")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print("INVALID: compiler identity unavailable")
        return 2
    print("compiler_release=" + release[0] + " default_target=" + host[0])
    print("upstream_manifest_pin=" + UPSTREAM)
    print("identity_scope=pinned_relevant_blobs_not_verified_checkouts")
    with tempfile.TemporaryDirectory(prefix="ai0-module-parity-") as temp:
        for case in CASES:
            directory = Path(temp) / case.label
            directory.mkdir()
            path = a.texture if case.source_pin == TEXTURE_PIN else a.primitive
            try:
                count, generated_blob = run_case(case, path, getattr(a, case.label), rustc, directory)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                print(case.label + " FAILED: no complete verified receipt")
                return 1
            print(f"{case.label} manifest_head={case.head} source_blob={case.source_pin} generated_blob={generated_blob} "
                  f"passed={count} candidate={case.candidate}")
    print("All three isolated raw-module suites passed; not native GPU/runtime acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
