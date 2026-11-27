# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile exact #69/#70 changes together in disposable prepared runtime.

This exercises existing native regression suites and builds, not a new
actual descriptor binding parity fixture. Never install or run a title.
"""
import argparse
import ast
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
SOURCE = "crates/victory-gpu/src/draw.rs"
PIN = "41380c23a61b93000c4886265c3063676ddc4864"
CASES = (
    ("24ae553e449bac498f29cde7395d6b6ef95ec888", "tools/preview_ai0_fresh_slot_set.py",
     "1772ffdfd7007a748d63284d675fe7cb789271fb"),
    ("1710d374f7d6c22b6ef158f2704fb0b5653ea91c", "tools/preview_ai0_root_constant_buffer.py",
     "0fd5b9cf3fa6f79d8398e74df77fcc652c65615c"),
)


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)


def anchors(path, case):
    head, script_path, pin = case
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
    p.add_argument("--pr69", type=Path, required=True)
    p.add_argument("--pr70", type=Path, required=True)
    a = p.parse_args()
    if os.name != "nt":
        raise SystemExit("Windows native toolchain required")
    changes = [anchors(path.resolve(), case) for path, case in zip((a.pr69, a.pr70), CASES)]
    with tempfile.TemporaryDirectory(prefix="ai1-descriptor-composition-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True)
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream mismatch")
        raw = git(target, "show", "HEAD:" + SOURCE)
        if blob(raw) != PIN:
            raise ValueError("raw draw source mismatch")
        path = target / SOURCE
        original = path.read_bytes()
        if b"\r\n" in original and b"\n" in original.replace(b"\r\n", b""):
            raise ValueError("mixed source line endings")
        prepared = original.replace(b"\r\n", b"\n")
        if b"\r" in prepared:
            raise ValueError("unexpected source line endings")
        text = prepared.decode()
        print(f"upstream={UPSTREAM} raw_draw_blob={PIN} prepared_draw_blob_lf={blob(prepared)}", flush=True)
        # Verify the exact old blocks in both raw and prepared sources.
        # The remaining prepared method tails are retained unchanged.
        for change in changes:
            apply(raw.decode(), change)
            text = apply(text, change)
        combined = text.encode()
        path.write_bytes(combined.replace(b"\n", b"\r\n") if b"\r\n" in original else combined)
        print(f"combined_draw_blob_lf={blob(combined)}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        subprocess.run([sys.executable, str(ROOT / "tools/ci_paired_tests.py"), str(target)], check=True)
    print("Combined native compile and existing regression gates passed; no binding parity or gameplay acceptance", flush=True)


if __name__ == "__main__":
    main()
