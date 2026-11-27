# SPDX-License-Identifier: GPL-3.0-or-later
"""Rehearse #82/#64/#65 together in scratch only, without title or installation."""
import argparse
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from apply_gpu_copy_perf import transform

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
SHADOW = "crates/victory-gpu/src/shadow.rs"
TEXTURE = "crates/victory-formats/src/texture.rs"
RAW_SHADOW = "4fa43df7932bb6692d164384cd28b1f08f3001ee"
PREPARED_SHADOW = "40f1ae02506de251d51e00ebfd36f58e58e7621b"
RAW_TEXTURE = "fa719c93953d9e6589c4d2cd27a13d773863c316"
CASES = (
    ("1b118a210d02d19686a9389fc30ea723c670bec4", "tools/preview_ai0_detile_run.py",
     "a120dd694f4c57256b9ad585dbaceadd0df2d21b"),
    ("5af0fa2cbadf311947f0101eefad18b16bcc2f9a", "tools/preview_ai0_spread_table.py",
     "e0770142d98be9fe7fe76ca6f29530f4a958010e"),
)
TEST87 = "shadow::card_merge_tests::ai1_first_slice_exact_partition"
TEST90 = "texture::ai1_composition::actual_combined_layout_copy_and_refusal_parity"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)


def pinned(path, head, file, expected):
    if git(path, "rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("checkout identity mismatch")
    data = git(path, "show", "HEAD:" + file)
    if blob(data) != expected:
        raise ValueError("blob identity mismatch: " + file)
    print(f"checkout={head} file={file} blob={expected}", flush=True)
    return data


def constants(source, names):
    out = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            key = node.targets[0]
            if isinstance(key, ast.Name) and key.id in names:
                if key.id in out:
                    raise ValueError("duplicate pinned constant")
                out[key.id] = ast.literal_eval(node.value)
    if set(out) != set(names):
        raise ValueError("missing pinned constants")
    return out


def normalize(raw):
    if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b""):
        raise ValueError("mixed line endings")
    data = raw.replace(b"\r\n", b"\n")
    if b"\r" in data:
        raise ValueError("unexpected CR")
    return data


def replace_once(source, old, new):
    if source.count(old) != 1 or new in source:
        raise ValueError("nonunique or changed source anchor")
    return source.replace(old, new, 1)


def write(path, data, original):
    path.write_bytes(data.replace(b"\n", b"\r\n") if b"\r\n" in original else data)


def test(target, package, pattern, expected, flags=(), exact=False):
    cmd = ["cargo", "test", "--locked", "-p", package, "--lib", *flags,
           pattern, "--", "--test-threads=1"]
    if exact:
        cmd.append("--exact")
    env = dict(os.environ, VICTORY_BACK_AVX2="0", VICTORY_BACK_SPARSE_MERGE="0")
    r = subprocess.run(cmd, cwd=target, env=env, capture_output=True,
                       text=True, errors="replace", timeout=3600)
    lines = r.stdout.splitlines()
    actual = [l for l in lines if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in lines if l.startswith("test result:")]
    summary = rf"test result: ok\. {len(expected)} passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if (r.returncode or len(actual) != len(expected)
            or set(actual) != {f"test {name} ... ok" for name in expected}
            or len(summaries) != 1 or not re.fullmatch(summary, summaries[0])):
        print((r.stderr + "\n" + r.stdout)[-16000:], flush=True)
        raise ValueError("missing exact combined native test receipt")
    print(f"package={package} flags={flags}", flush=True)
    for line in actual + summaries:
        print(line, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for label in ("pr87", "pr90", "pr64", "pr65"):
        p.add_argument("--" + label, type=Path, required=True)
    a = p.parse_args()
    if os.name != "nt":
        raise SystemExit("Windows native toolchain required")
    cmp = constants(pinned(a.pr87, "4248ed701ff0f4ad984b9d694642461e43a5f7e1",
        "tools/validate_ai1_compare_first_slice.py", "d827521370993e267e3dcacd3abf08bbc14a9c63"),
        ("OLD", "NEW", "ANCHOR", "FIXTURE"))
    tex = constants(pinned(a.pr90, "573b2d5be276e80572f9548fc6dc187ea0b63dc2",
        "tools/validate_ai1_texture_composition.py", "c295928c294f5194dd7ddc0f8411c2cbfe0283b9"),
        ("BASE_TESTS",))
    fixture = pinned(a.pr90, "573b2d5be276e80572f9548fc6dc187ea0b63dc2",
        "probes/ai1_texture_composition.rs", "8523f85ad032050819619182bc1e92246d4d0864").decode()
    changes = [constants(pinned(path, *case), ("OLD", "NEW"))
               for path, case in zip((a.pr64, a.pr65), CASES)]
    with tempfile.TemporaryDirectory(prefix="ai1-memory-texture-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"),
                        str(target), "--paired-wave-refresh"], check=True)
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream mismatch")
        raw = git(target, "show", "HEAD:" + SHADOW)
        path = target / SHADOW
        original = path.read_bytes()
        prepared = normalize(original)
        if (blob(raw) != RAW_SHADOW or blob(prepared) != PREPARED_SHADOW
                or prepared != transform(raw.decode()).encode()):
            raise ValueError("prepared shadow mismatch")
        shadow = replace_once(prepared.decode(), cmp["OLD"], cmp["NEW"])
        # The insertion contains its anchor; validate separately.
        if shadow.count(cmp["ANCHOR"]) != 1 or "fn ai1_first_slice_exact_partition(" in shadow:
            raise ValueError("shadow fixture anchor mismatch")
        shadow = shadow.replace(cmp["ANCHOR"], cmp["ANCHOR"] + "\n" + cmp["FIXTURE"], 1)
        write(path, shadow.encode(), original)
        print(f"shadow_prepared={PREPARED_SHADOW} shadow_combined={blob(shadow.encode())}", flush=True)

        raw = git(target, "show", "HEAD:" + TEXTURE)
        path = target / TEXTURE
        original = path.read_bytes()
        if blob(raw) != RAW_TEXTURE or normalize(original) != raw:
            raise ValueError("prepared texture mismatch")
        candidate = replace_once(raw.decode(), changes[0]["OLD"], changes[0]["NEW"])
        new = changes[1]["NEW"].replace("fn spread_incremental(", "fn spread(", 1)
        candidate = replace_once(candidate, changes[1]["OLD"], new)
        baseline = path.with_name("ai1_rehearsal_texture_baseline.rs")
        with baseline.open("xb") as out:
            out.write(raw)
        if fixture.count('path = "baseline.rs"') != 1:
            raise ValueError("texture fixture path anchor mismatch")
        fixture = fixture.replace('path = "baseline.rs"', 'path = "ai1_rehearsal_texture_baseline.rs"', 1)
        texture = candidate.encode() + b"\n" + fixture.encode()
        write(path, texture, original)
        print(f"texture_prepared={RAW_TEXTURE} texture_combined={blob(texture)}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for flags in ((), ("--release",), ("--features", "diagnostics")):
            test(target, "victory-gpu", TEST87, {TEST87}, flags, exact=True)
        names = {"texture::tests::" + n for n in tex["BASE_TESTS"]} | {
            "texture::baseline::tests::" + n for n in tex["BASE_TESTS"]} | {TEST90}
        for flags in ((), ("--release",)):
            test(target, "victory-formats", "texture::", names, flags)
        subprocess.run([sys.executable, str(ROOT / "tools/ci_paired_tests.py"), str(target)], check=True)
    print("Combined scratch rehearsal passed; no production or gameplay acceptance", flush=True)


if __name__ == "__main__":
    main()
