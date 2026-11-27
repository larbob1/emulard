# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile exact #66/#67 changes in a disposable prepared runtime.

Exercise actual primitive expansion and existing native regression gates.
This does not prove actual draw caller or scratch lifetime parity.
Never install or run a title.
"""
import argparse
import ast
import hashlib
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
CASES = (
    ("3b22fabc99cef39f20b87abe67e8e4e1a9c0e6c1", "tools/preview_ai0_rect_copy.py",
     "86b4f8ef68424aedfe98403d69993e0f5aa1f6e6",
     "crates/victory-gpu/src/primitive.rs", "3f73ee71ec98b59472be17fbf48f9198424fcb74"),
    ("2d97a632ce340e84e8bb04b26aaab211b8dd6e3b", "tools/preview_ai0_rect_slot_mask.py",
     "a78a1fbe92b4151d949866651948259181818b41",
     "crates/victory-gpu/src/draw.rs", "41380c23a61b93000c4886265c3063676ddc4864"),
)
FIXTURE_PIN = "001e8b74307545af3dbd63576bcb1a4bbb119c97"
TEST = "primitive::ai0_rect_copy_review::actual_rectangle_expansion_parity"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)


def anchors(path, case):
    head, script_path, pin, _, _ = case
    if git(path, "rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("proposal head mismatch")
    raw = git(path, "show", "HEAD:" + script_path)
    if blob(raw) != pin:
        raise ValueError("proposal blob mismatch")
    values = {}
    for node in ast.parse(raw).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in ("START", "END", "OLD", "NEW"):
                if t.id in values:
                    raise ValueError("duplicate anchor")
                values[t.id] = ast.literal_eval(node.value)
    if set(values) != {"START", "END", "OLD", "NEW"} or not all(isinstance(v, str) for v in values.values()):
        raise ValueError("missing proposal anchor")
    print(f"proposal={head} preview_blob={pin}", flush=True)
    return values


def apply(source, a):
    start, end, old, new = (a[k] for k in ("START", "END", "OLD", "NEW"))
    if any(source.count(x) != 1 for x in (start, end, old)) or new in source:
        raise ValueError("ambiguous or changed prepared source anchor")
    i = source.index(start)
    j = source.index(end, i)
    k = source.index(old)
    if not i <= k < k + len(old) <= j:
        raise ValueError("replacement outside reviewed method")
    return source[:k] + new + source[k+len(old):]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pr66", type=Path, required=True)
    p.add_argument("--pr67", type=Path, required=True)
    a = p.parse_args()
    if os.name != "nt":
        raise SystemExit("Windows native toolchain required")
    changes = [anchors(path.resolve(), case) for path, case in zip((a.pr66, a.pr67), CASES)]
    with tempfile.TemporaryDirectory(prefix="ai1-vertex-composition-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True)
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream mismatch")
        for case, change in zip(CASES, changes):
            _, _, _, source, pin = case
            raw = git(target, "show", "HEAD:" + source)
            if blob(raw) != pin:
                raise ValueError("raw source mismatch: " + source)
            path = target / source
            original = path.read_bytes()
            if b"\r\n" in original and b"\n" in original.replace(b"\r\n", b""):
                raise ValueError("mixed source line endings")
            prepared = original.replace(b"\r\n", b"\n")
            if b"\r" in prepared:
                raise ValueError("unexpected source line endings")
            text = prepared.decode()
            print(f"upstream={UPSTREAM} source={source} raw_blob={pin} prepared_blob_lf={blob(prepared)}", flush=True)
            apply(raw.decode(), change)
            combined = apply(text, change)
            if source.endswith("/primitive.rs"):
                if prepared != raw:
                    raise ValueError("prepared primitive source changed")
                # Keep an exact copy of the original function for the
                # existing reviewed parity fixture. Actual expand_rects
                # is the candidate, not a separate unused helper.
                i = text.index(change["START"])
                j = text.index(change["END"], i) + len("\n}")
                baseline = text[i:j].replace(change["START"],
                    "fn expand_rects_baseline(", 1)
                fixture = git(a.pr66.resolve(), "show", "HEAD:probes/rect_copy_review.rs")
                if blob(fixture) != FIXTURE_PIN:
                    raise ValueError("primitive fixture pin mismatch")
                fixture = fixture.decode()
                if fixture.count("expand_rects(&src") != 1 or fixture.count("expand_rects_coalesced(&src") != 1:
                    raise ValueError("primitive fixture call anchors changed")
                fixture = fixture.replace("expand_rects(&src", "expand_rects_baseline(&src", 1)
                fixture = fixture.replace("expand_rects_coalesced(&src", "expand_rects(&src", 1)
                combined += "\n#[cfg(test)]\n" + baseline + "\n" + fixture
            combined = combined.encode()
            path.write_bytes(combined.replace(b"\n", b"\r\n") if b"\r\n" in original else combined)
            print(f"source={source} combined_blob_lf={blob(combined)}", flush=True)
        for release in (False, True):
            args = ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib"]
            if release:
                args.append("--release")
            args.extend([TEST, "--", "--exact", "--test-threads=1"])
            result = subprocess.run(args, cwd=target, capture_output=True,
                                    text=True, errors="replace", timeout=3600)
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            expected = f"test {TEST} ... ok"
            summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
            if (result.returncode != 0 or lines.count(expected) != 1
                    or len([l for l in lines if l.startswith("test result:")]) != 1
                    or not any(re.fullmatch(summary,l) for l in lines)):
                print((result.stderr + "\n" + result.stdout)[-16000:], flush=True)
                raise ValueError("missing exact primitive parity receipt")
            print(("release" if release else "debug") + " " + expected, flush=True)
            print(next(l for l in lines if l.startswith("test result:")), flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        subprocess.run([sys.executable, str(ROOT / "tools/ci_paired_tests.py"), str(target)], check=True)
    print("Combined native compile, primitive parity and existing regression gates passed; no actual draw caller or gameplay acceptance", flush=True)


if __name__ == "__main__":
    main()
