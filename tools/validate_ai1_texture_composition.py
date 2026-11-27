# SPDX-License-Identifier: GPL-3.0-or-later
"""Compose exact reviewed #64/#65 changes only in a disposable source module."""
import argparse
import ast
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
SOURCE = "crates/victory-formats/src/texture.rs"
PIN = "fa719c93953d9e6589c4d2cd27a13d773863c316"
CASES = (
    ("1b118a210d02d19686a9389fc30ea723c670bec4", "tools/preview_ai0_detile_run.py",
     "a120dd694f4c57256b9ad585dbaceadd0df2d21b"),
    ("5af0fa2cbadf311947f0101eefad18b16bcc2f9a", "tools/preview_ai0_spread_table.py",
     "e0770142d98be9fe7fe76ca6f29530f4a958010e"),
)
BASE_TESTS = {
    "extents_past_the_hardware_limit_are_invalid",
    "blocks_hold_their_size_in_elements",
    "addresses_are_a_bijection_and_copies_round_trip",
    "tiled_chunks_match_element_offsets_with_odd_row_pitches",
    "hand_checked_addresses", "mip_tail_comes_first",
    "depth_stencil_is_two_planes", "texture_copies_reject_overflowing_pitches",
    "volume_copy_rejects_overflowing_depth_pitch",
    "bad_descriptions_and_buffers_are_refused",
}
EXPECTED = {"tests::" + name for name in BASE_TESTS} | {
    "baseline::tests::" + name for name in BASE_TESTS
} | {"ai1_composition::actual_combined_layout_copy_and_refusal_parity"}


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)


def blocks(path, case):
    head, script_path, pin = case
    if git(path, "rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("proposal head mismatch")
    script = git(path, "show", "HEAD:" + script_path)
    if blob(script) != pin:
        raise ValueError("proposal blob mismatch")
    values = {}
    for node in ast.parse(script).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in ("OLD", "NEW"):
                if target.id in values:
                    raise ValueError("duplicate proposal anchor")
                values[target.id] = ast.literal_eval(node.value)
    if set(values) != {"OLD", "NEW"} or not all(isinstance(v, str) for v in values.values()):
        raise ValueError("proposal anchors missing")
    print(f"proposal={head} preview_blob={pin}", flush=True)
    return values["OLD"], values["NEW"]


def replace_once(source, old, new):
    if source.count(old) != 1 or new in source:
        raise ValueError("candidate anchor mismatch")
    return source.replace(old, new, 1)


def run(args, cwd, timeout):
    result = subprocess.run(args, cwd=cwd, capture_output=True,
                            text=True, errors="replace", timeout=timeout)
    if result.returncode:
        print((result.stdout + "\n" + result.stderr)[-16000:], flush=True)
        raise ValueError("compiler/test command failed")
    return [l for l in result.stdout.splitlines() if l.strip()]


def verify(source, directory, optimized):
    executable = directory / ("optimized-tests" if optimized else "debug-tests")
    args = ["rustc", "--edition=2021", "--test", str(source), "-o", str(executable)]
    if optimized:
        args.extend(["-C", "opt-level=3", "-C", "overflow-checks=on"])
    run(args, directory, 180)
    listing = run([str(executable), "--list"], directory, 30)
    if len(listing) != len(EXPECTED) + 1 or set(listing[:-1]) != {
            n + ": test" for n in EXPECTED} or listing[-1] != f"{len(EXPECTED)} tests, 0 benchmarks":
        raise ValueError("unexpected complete test inventory")
    output = run([str(executable), "--test-threads=1", "--format=pretty"], directory, 180)
    names = {f"test {n} ... ok" for n in EXPECTED}
    summary = rf"test result: ok\. {len(EXPECTED)} passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in \d+(?:\.\d+)?s"
    if (len(output) != len(EXPECTED) + 2 or output[0] != f"running {len(EXPECTED)} tests"
            or set(output[1:-1]) != names or not re.fullmatch(summary, output[-1])):
        raise ValueError("incomplete or unexpected test receipt")
    print(("optimized" if optimized else "debug") + " complete receipt:", flush=True)
    for line in output:
        print(line, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pr64", type=Path, required=True)
    p.add_argument("--pr65", type=Path, required=True)
    a = p.parse_args()
    changes = [blocks(path.resolve(), case) for path, case in zip((a.pr64, a.pr65), CASES)]
    with tempfile.TemporaryDirectory(prefix="ai1-texture-composition-") as tmp:
        directory = Path(tmp)
        target = directory / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True)
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream mismatch")
        raw = git(target, "show", "HEAD:" + SOURCE)
        prepared = (target / SOURCE).read_bytes()
        if blob(raw) != PIN or prepared != raw:
            raise ValueError("prepared texture source differs from pinned raw input")
        print(f"upstream={UPSTREAM} prepared_blob={blob(prepared)}", flush=True)
        original = prepared.decode()
        candidate = replace_once(original, *changes[0])
        old, new = changes[1]
        # The preview names the extra function spread_incremental. Use
        # the original name in the disposable combined module so the
        # actual Layout::new constructor calls the candidate directly.
        new = new.replace("fn spread_incremental(", "fn spread(", 1)
        candidate = replace_once(candidate, old, new)
        fixture = (ROOT / "probes/ai1_texture_composition.rs").read_bytes()
        (directory / "baseline.rs").write_bytes(raw)
        source = directory / "combined.rs"
        source.write_bytes(candidate.encode() + b"\n" + fixture)
        print(f"combined_blob={blob(source.read_bytes())} fixture_blob={blob(fixture)}", flush=True)
        verify(source, directory, False)
        verify(source, directory, True)
    print("Combined prepared-source standalone parity only; no whole-runtime/GPU acceptance")


if __name__ == "__main__":
    main()
