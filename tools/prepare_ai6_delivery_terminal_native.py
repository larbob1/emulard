#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the native fixture on a disposable, already preview-patched runtime."""
import argparse
import difflib
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import prepare_ai6_delivery_terminal_preview as core

FIXTURE = "probes/ai6_delivery_terminal_native.rs"
FIXTURE_PIN = "c68ea7d17541a4d5ffc3c5e178016b06299cd1f0"
MODULE_POST = "88abde5c80dab3a95de9e9c2986c3b17dc51185f"
CORE_PINS = {
    "tools/prepare_ai6_delivery_terminal_preview.py": "0987a77453a850d6f91214324b4724a1a548a4ef",
    "patches/ai6-delivery-terminal-preview.patch": "5342aa50c85b607977e25fbcb1fc7c58d4445054",
    "docs/ai6-delivery-terminal-preview.md": "a16125fa1e6d73c0cd5e82086df0423216e25b90",
}
ANCHOR = b"    if unsafe { TerminateProcess(GetCurrentProcess(), DELIVERY_UNRESOLVED) } == 0 {"
HOOK = b"    #[cfg(test)]\n    ai6_delivery_terminal_native::observe_boundary(state);\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    ns = parser.parse_args()
    try:
        if sys.version_info < (3, 12):
            raise ValueError("Python 3.12+ required")
        root = ns.checkout.absolute()
        own = Path(__file__).resolve().parent.parent
        if root == own or root in own.parents or own in root.parents:
            raise ValueError("Use a separate disposable prepared checkout")
        for path, pin in CORE_PINS.items():
            if core.blob(core.lf((own / path).read_bytes())) != pin:
                raise ValueError("Frozen core input mismatch: " + path)
        fixture = core.lf((own / FIXTURE).read_bytes())
        if core.blob(fixture) != FIXTURE_PIN or not fixture.endswith(b"\n"):
            raise ValueError("Fixture input mismatch")
        identity = core.root_identity(root)

        def snapshot():
            if core.root_identity(root) != identity:
                raise ValueError("Checkout root identity changed")
            result = core.inventory(root)
            if core.root_identity(root) != identity:
                raise ValueError("Checkout root identity changed")
            return result

        before = snapshot()
        for path in (core.LIB, core.MODULE):
            if before.get(path, (None,))[0] != "file":
                raise ValueError("Missing core preview path: " + path)
        if core.blob(core.lf((root / core.LIB).read_bytes())) != core.POST:
            raise ValueError("Wrong preview lib postimage")
        old = (root / core.MODULE).read_bytes()
        if old != core.lf(old) or core.blob(old) != core.NEW:
            raise ValueError("Require exact LF preview module preimage")
        if old.count(ANCHOR) != 1 or not old.endswith(b"\n"):
            raise ValueError("Unique supervisor boundary required")
        new = old.replace(ANCHOR, HOOK + ANCHOR)
        new += b"\n#[cfg(test)]\nmod ai6_delivery_terminal_native {\n" + fixture + b"}\n"
        if core.blob(new) != MODULE_POST:
            raise ValueError("Unexpected fixture module postimage")
        patch = "".join(difflib.unified_diff(
            old.decode("utf-8").splitlines(keepends=True),
            new.decode("utf-8").splitlines(keepends=True),
            fromfile="a/" + core.MODULE, tofile="b/" + core.MODULE,
        )).encode("utf-8")
        core.git(root, "apply", "--check", "-", data=patch)
        if snapshot() != before:
            raise ValueError("Dry check changed checkout; discard checkout")
        if not ns.apply:
            print("Dry check: exact native fixture pre/post pins and unchanged inventory")
            return 0

        def apply_and_verify():
            core.git(root, "apply", "-", data=patch)
            after = snapshot()
            if (root / core.MODULE).read_bytes() != new:
                raise ValueError("Unexpected actual module postimage")
            expected = dict(before)
            expected[core.MODULE] = after[core.MODULE]
            if after != expected:
                raise ValueError("Unexpected inventory delta; discard checkout")
            return after

        after = apply_and_verify()
        core.git(root, "apply", "--reverse", "--check", "-", data=patch)
        if snapshot() != after:
            raise ValueError("Reverse check changed checkout")
        core.git(root, "apply", "--reverse", "-", data=patch)
        if snapshot() != before or (root / core.MODULE).read_bytes() != old:
            raise ValueError("Inverse failed to restore original inventory")
        if apply_and_verify() != after:
            raise ValueError("Reapply failed to reproduce postinventory")
        core.git(root, "diff", "--check")
        if snapshot() != after:
            raise ValueError("Final inventory changed")
        print("Applied native fixture: exact one-path inventory delta and inverse/reapply")
        return 0
    except (OSError, ValueError, UnicodeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Terminal native preparation failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
