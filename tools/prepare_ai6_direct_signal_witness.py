#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the isolated AI6 D0/D1/I0 direct signal witness fixture, never a runtime patch.

Requires an already prepared disposable paired-wave checkout. No builder,
compiler, test, native workflow, or title invocation occurs here.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
PREFIX = "crates/victory-gpu/src/"
# raw upstream blob, expected prepared LF blob (host independently native-
# verified in #111; queue/list/fence/device predictions must match actual).
PINS = {
    "queue.rs": ("c0adc57c4df4494598022dbc73f1f0a69308fdaa",
                 "af59e827f75e050e3be49722ab0a704c0ec6cbb6"),
    "host.rs": ("458d146aedf6f13dac80782d283a048d80e4a931",
                "88acbb3b2cf550cdf2303685fcc32249f9e46328"),
    "list.rs": ("3bf89f3c9b17f14c2ec4fa4480e3378e6ac8857e",)*2,
    "fence.rs": ("b82033550223aa628bd75a700c22465f3a5ca389",)*2,
    "device.rs": ("dfbf2b2253a8f739e418e7fbcc3a810a66e19252",)*2,
    "shadow.rs": ("4fa43df7932bb6692d164384cd28b1f08f3001ee",
                  "40f1ae02506de251d51e00ebfd36f58e58e7621b"),
}
FIXTURES = {
    "queue.rs": ("ai6_direct_signal_witness.rs", "a3c4a0c4d51c24b0c723177d4bc83958962b843a"),
    "host.rs": ("ai6_direct_signal_witness_host.rs", "3dd62952b7752aeb528364ecacaf077ac2e4727c"),
}

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def lf(data):
    return data.replace(b"\r\n", b"\n")

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])

# Exact, scope-limited observations. Test cfg only; wait result is still
# ignored in the uninstrumented build. No production policy change.
HOST = [
    [
        "                        WaitForSingleObject(self.event, INFINITE);\n                        stood(started);\n                        working(true);\n                    }\n                    Err(e) => tracing::warn!(error = %e, \"host submission not waited for\"),",
        "                        let waited = WaitForSingleObject(self.event, INFINITE);\n                        #[cfg(all(test, feature = \"diagnostics\"))]\n                        ai6_direct_signal_witness_wait_result(waited.0 == 0);\n                        let _ = waited;\n                        stood(started);\n                        working(true);\n                    }\n                    Err(e) => {\n                        #[cfg(all(test, feature = \"diagnostics\"))]\n                        ai6_direct_signal_witness_wait_result(false);\n                        tracing::warn!(error = %e, \"host submission not waited for\");\n                    }"
    ],
    [
        "        let _ = &firsts;\n        FINISHED.store(this_submission, Ordering::Release);\n        bury(this_submission);",
        "        let _ = &firsts;\n        #[cfg(all(test, feature = \"diagnostics\"))]\n        ai6_direct_signal_witness_before_retire(self, *submitted);\n        FINISHED.store(this_submission, Ordering::Release);\n        bury(this_submission);"
    ],
    [
        "    for (buffer, at, [row, rows, pitch]) in &list.deferred().backs {\n        let mut data = std::ptr::null_mut();",
        "    for (buffer, at, [row, rows, pitch]) in &list.deferred().backs {\n        #[cfg(all(test, feature = \"diagnostics\"))]\n        if crate::queue::ai6_direct_signal_witness::select(buffer, *at, *row, *rows, *pitch) {\n            continue;\n        }\n        let mut data = std::ptr::null_mut();"
    ],
    [
        "        copy_back(0, copying.elapsed().as_micros() as u64);\n        for list in runs {\n            // Read backs first: a value written at the bottom of the pipe\n            // may be what tells the title that they are there.\n            read_backs(list);\n            for &(at, what, bytes) in &list.deferred().writes {\n                what.write(at as *mut u8, bytes);\n            }\n        }\n        self.log_messages();",
        "        copy_back(0, copying.elapsed().as_micros() as u64);\n        for list in runs {\n            // Read backs first: a value written at the bottom of the pipe\n            // may be what tells the title that they are there.\n            read_backs(list);\n            #[cfg(all(test, feature = \"diagnostics\"))]\n            ai6_direct_signal_witness_readback(list);\n            for &(at, what, bytes) in &list.deferred().writes {\n                what.write(at as *mut u8, bytes);\n            }\n        }\n        self.log_messages();"
    ]
]
QUEUE = []

def inject(original, changes, fixture):
    result = original
    for old, new in changes:
        old, new = old.encode(), new.encode()
        if result.count(old) != 1 or result.count(new):
            raise ValueError("observer anchor absent, duplicate or already applied")
        result = result.replace(old, new, 1)
    result += b"\n" + fixture
    restored = result[:-len(fixture)-1]
    for old, new in reversed(changes):
        old, new = old.encode(), new.encode()
        if restored.count(new) != 1:
            raise ValueError("nonunique inverse anchor")
        restored = restored.replace(new, old, 1)
    if restored != original:
        raise ValueError("observer/append inverse did not restore input")
    return result

def inventory(root):
    result = {}
    def walk(directory):
        for path in sorted(directory.iterdir()):
            rel = path.relative_to(root).as_posix()
            if rel == ".git":
                continue
            if path.is_symlink() or path.is_junction():
                raise ValueError("linked path in scratch tree: " + rel)
            if path.is_dir():
                result[rel] = ("dir",)
                walk(path)
            elif path.is_file():
                with path.open("rb") as stream:
                    result[rel] = ("file", hashlib.file_digest(stream, "sha256").hexdigest())
            else:
                raise ValueError("unexpected scratch path type: " + rel)
    walk(root)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="write only the two scratch sources after all checks")
    args = parser.parse_args()
    try:
        supplied = args.checkout.absolute()
        if supplied.is_symlink() or supplied.is_junction() or not supplied.is_dir():
            raise ValueError("expected plain scratch directory")
        root = supplied.resolve(strict=True)
        git_root = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve(strict=True)
        if root == ROOT or ROOT in root.parents or root in ROOT.parents or not root.samefile(git_root):
            raise ValueError("expected independent disposable Git checkout root")
        if git(root, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("wrong pinned upstream HEAD")
        if blob(lf((ROOT / "tools/build_runtime.py").read_bytes())) != BUILDER:
            raise ValueError("wrong builder identity")
        before = inventory(root)
        originals = {}
        for name, (raw, prepared) in PINS.items():
            if blob(git(root, "show", f"HEAD:{PREFIX}{name}")) != raw:
                raise ValueError(f"wrong raw {name}")
            path = root / (PREFIX + name)
            if path.is_symlink():
                raise ValueError(f"symlinked source {name}")
            disk = path.read_bytes()
            normalized = lf(disk)
            if blob(normalized) != prepared:
                raise ValueError(f"wrong actual prepared {name}: {blob(normalized)}")
            originals[name] = (disk, normalized)
            print(f"source={name} raw={raw} prepared={prepared} bytes={len(normalized)}")
        outputs = {}
        for name, changes in (("queue.rs", QUEUE), ("host.rs", HOST)):
            file, expected = FIXTURES[name]
            fixture = lf((ROOT / "probes" / file).read_bytes())
            if blob(fixture) != expected:
                raise ValueError(f"wrong fixture {file}")
            disk, normalized = originals[name]
            if b"ai6_direct_signal_witness" in normalized:
                raise ValueError("fixture already present")
            after = inject(normalized, changes, fixture)
            expected_post = {
                "queue.rs": "a00dd7fb283b4c13de6f0dae781130331e5d9434",
                "host.rs": "bc419ee340a05a1732c5272955b76919adb24952",
            }[name]
            if blob(after) != expected_post:
                raise ValueError(f"{name} postimage differs from reconstructed pin")
            print(f"fixture={file} blob={expected} post={blob(after)} bytes={len(after)}")
            outputs[name] = after.replace(b"\n", b"\r\n") if b"\r\n" in disk else after
        if inventory(root) != before:
            raise ValueError("scratch inventory changed before write")
        if args.apply:
            for name in originals:
                if (root / (PREFIX + name)).read_bytes() != originals[name][0]:
                    raise ValueError(f"source changed after preflight: {name}")
            # Disposable checkout only. On I/O failure retain evidence; no
            # automatic retry or compilation of a partially modified tree.
            for name, data in outputs.items():
                path = root / (PREFIX + name)
                path.write_bytes(data)
                written = path.read_bytes()
                if written != data or blob(lf(written)) != blob(lf(data)):
                    raise ValueError(f"written postimage differs: {name}")
            for name in originals.keys() - outputs.keys():
                if (root / (PREFIX + name)).read_bytes() != originals[name][0]:
                    raise ValueError(f"untouched source changed: {name}")
            after = inventory(root)
            expected_delta = {PREFIX + name for name in outputs}
            if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != expected_delta:
                raise ValueError("unexpected full scratch inventory delta")
            print(f"inventory_entries={len(before)} changed=2")
            print("applied two scratch-only observer/fixture files")
        else:
            print("dry run; no files written")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"AI6 scratch preparation refused: {exc}\n")

if __name__ == "__main__":
    main()
