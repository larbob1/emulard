# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable production-only control/combined rehearsal; no builder registration."""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
PREVIEW_HEAD = "773f539df1275e7dc29a6f3000d35060c6a60e8b"
PREVIEW_BLOB = "87aa776d0528e217f71b4f2e78512637957fb236"
PREVIEW_PATH = "tools/preview_ai1_port_contract.py"
SHADOW = "crates/victory-gpu/src/shadow.rs"
TEXTURE = "crates/victory-formats/src/texture.rs"
BEFORE = {
    SHADOW: "40f1ae02506de251d51e00ebfd36f58e58e7621b",
    TEXTURE: "fa719c93953d9e6589c4d2cd27a13d773863c316",
}
AFTER = {
    SHADOW: "7229972b47fc789ec2c9968f48b41db6b8e785f0",
    TEXTURE: "9d5f96c702a0a125f04bd34d4247091a3e23c131",
}


def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd)


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def lf(data):
    if b"\r\n" in data and b"\n" in data.replace(b"\r\n", b""):
        raise ValueError("mixed line endings")
    result = data.replace(b"\r\n", b"\n")
    if b"\r" in result:
        raise ValueError("unexpected CR")
    return result


def source_inventory(target):
    names = set(git(target, "ls-files", "-z", "--cached",
                    "--others", "--exclude-standard").split(b"\0"))
    result = {}
    for raw in sorted(filter(None, names)):
        name = os.fsdecode(raw)
        path = target / name
        if path.is_symlink():
            result[name] = ("link", os.readlink(path))
        elif path.is_file() and path.resolve().is_relative_to(target):
            mode = stat.S_IMODE(path.stat().st_mode)
            result[name] = ("file", mode, hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            raise ValueError("unexpected source inventory entry: " + name)
    return result


def load_preview(checkout):
    if git(checkout, "rev-parse", "HEAD").decode().strip() != PREVIEW_HEAD:
        raise ValueError("preview checkout mismatch")
    raw = git(checkout, "show", "HEAD:" + PREVIEW_PATH)
    if blob(raw) != PREVIEW_BLOB:
        raise ValueError("preview blob mismatch")
    # Execute only the exact independently reviewed canonical module,
    # not arbitrary working-tree content. Its CLI entrypoint is disabled.
    scope = {"__name__": "pinned_ai1_preview"}
    exec(compile(raw, PREVIEW_PATH, "exec"), scope)
    return scope["calculate"]


def arm(target, combined, calculate):
    subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"),
                    str(target), "--paired-wave-refresh"], check=True)
    target = target.resolve(strict=True)
    if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
        raise ValueError("runtime revision mismatch")
    before = source_inventory(target)
    original = {}
    for name, expected in BEFORE.items():
        path = target / name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(target):
            raise ValueError("unsafe source path")
        original[name] = path.read_bytes()
        if blob(lf(original[name])) != expected:
            raise ValueError("prepared source mismatch: " + name)
    result, receipt = calculate(original, combined, combined, combined)
    expected = AFTER if combined else BEFORE
    if set(result) != set(expected) or any(blob(result[n]) != h for n, h in expected.items()):
        raise ValueError("unexpected production-only postimage")
    want = set(expected) if combined else set()
    if set(receipt["would_change"]) != want:
        raise ValueError("selection inventory mismatch")
    # Both inputs and outputs checked before any write. Scratch is discarded
    # on failure; no in-place rollback of an installed runtime.
    for name in sorted(want):
        data = result[name]
        if b"\r\n" in original[name]:
            data = data.replace(b"\n", b"\r\n")
        (target / name).write_bytes(data)
    after = source_inventory(target)
    if before.keys() != after.keys():
        raise ValueError("source inventory changed")
    changed = {name for name in before if before[name] != after[name]}
    if changed != want:
        raise ValueError("unexpected changed paths")
    for name, h in expected.items():
        if blob(lf((target / name).read_bytes())) != h:
            raise ValueError("materialized source mismatch")
    subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
    print(f"arm={'111' if combined else '000'} source_count={len(after)} changed={sorted(changed)}", flush=True)
    for name, h in expected.items():
        print(f"production_only={name} blob_lf={h}", flush=True)
    # Existing native suites and both builds; no new regression fixture
    # inserted. The targeted #93 test receipts are separate evidence.
    subprocess.run([sys.executable, str(ROOT / "tools/ci_paired_tests.py"),
                    str(target)], check=True)
    if source_inventory(target) != after:
        raise ValueError("native validation changed source inventory")
    print(f"arm={'111' if combined else '000'} native regression and builds passed", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview", type=Path, required=True)
    p.add_argument("--arm", choices=("000", "111"), required=True)
    a = p.parse_args()
    if os.name != "nt":
        raise SystemExit("Windows native toolchain required")
    calculate = load_preview(a.preview.resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="ai1-production-only-") as tmp:
        arm(Path(tmp) / "runtime", a.arm == "111", calculate)
    print("Production-only scratch rehearsal; no registration, install or gameplay acceptance")


if __name__ == "__main__":
    main()
