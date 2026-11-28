#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the isolated AI6 positive-route fixture, never a runtime patch.

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
}
FIXTURES = {
    "queue.rs": ("ai6_dependent_consumer.rs", "755602d634e6e6c083c7f88611a17a44306cbc76"),
    "host.rs": ("ai6_dependent_consumer_host.rs", "facafd3fcaa231cd04c8002bb1dae95205f7966c"),
}

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def lf(data):
    return data.replace(b"\r\n", b"\n")

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])

# Exact, scope-limited observations. Test cfg only; wait result is still
# ignored in the uninstrumented build. No production policy change.
HOST = (
    (
        """                        WaitForSingleObject(self.event, INFINITE);
                        stood(started);
                        working(true);
                    }
                    Err(e) => tracing::warn!(error = %e, "host submission not waited for"),""",
        """                        let waited = WaitForSingleObject(self.event, INFINITE);
                        #[cfg(all(test, feature = "diagnostics"))]
                        ai6_dependent_consumer_wait_result(waited.0 == 0);
                        let _ = waited;
                        stood(started);
                        working(true);
                    }
                    Err(e) => {
                        #[cfg(all(test, feature = "diagnostics"))]
                        ai6_dependent_consumer_wait_result(false);
                        tracing::warn!(error = %e, "host submission not waited for");
                    }""",
    ),
    (
        """        let _ = &firsts;
        FINISHED.store(this_submission, Ordering::Release);
        bury(this_submission);""",
        """        let _ = &firsts;
        #[cfg(all(test, feature = "diagnostics"))]
        ai6_dependent_consumer_before_retire(self, *submitted);
        FINISHED.store(this_submission, Ordering::Release);
        bury(this_submission);""",
    ),
    (
        """        copy_back(0, copying.elapsed().as_micros() as u64);
        for list in runs {
            // Read backs first: a value written at the bottom of the pipe
            // may be what tells the title that they are there.
            read_backs(list);
            for &(at, what, bytes) in &list.deferred().writes {""",
        """        copy_back(0, copying.elapsed().as_micros() as u64);
        for list in runs {
            // Read backs first: a value written at the bottom of the pipe
            // may be what tells the title that they are there.
            read_backs(list);
            #[cfg(all(test, feature = "diagnostics"))]
            crate::queue::ai6_dependent_consumer::readback();
            for &(at, what, bytes) in &list.deferred().writes {""",
    ),
)
QUEUE = (
    (
        """                    Held::Value(wait) => {
                        // Passed at a present without being met:""",
        """                    Held::Value(wait) => {
                        #[cfg(all(test, feature = "diagnostics"))]
                        ai6_dependent_consumer::released(q, &wait, all);
                        // Passed at a present without being met:""",
    ),
    (
        """                    Held::Signal(fence, value) => {
                        if !joined.is_empty() {""",
        """                    Held::Signal(fence, value) => {
                        #[cfg(all(test, feature = "diagnostics"))]
                        ai6_dependent_consumer::before_signal(q, fence, value, all);
                        if !joined.is_empty() {""",
    ),
)

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

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="write only the two scratch sources after all checks")
    args = parser.parse_args()
    try:
        root = args.checkout.resolve(strict=True)
        if root == ROOT or git(root, "rev-parse", "--show-toplevel").decode().strip().replace("\\", "/").lower() != root.as_posix().lower():
            raise ValueError("expected independent disposable Git checkout root")
        if git(root, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("wrong pinned upstream HEAD")
        if blob(lf((ROOT / "tools/build_runtime.py").read_bytes())) != BUILDER:
            raise ValueError("wrong builder identity")
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
            if b"ai6_dependent_consumer" in normalized:
                raise ValueError("fixture already present")
            after = inject(normalized, changes, fixture)
            print(f"fixture={file} blob={expected} post={blob(after)} bytes={len(after)}")
            outputs[name] = after.replace(b"\n", b"\r\n") if b"\r\n" in disk else after
        if args.apply:
            for name, data in outputs.items():
                if (root / (PREFIX + name)).read_bytes() != originals[name][0]:
                    raise ValueError(f"source changed after preflight: {name}")
            # Disposable checkout only. On I/O failure retain evidence; no
            # automatic retry or compilation of a partially modified tree.
            for name, data in outputs.items():
                path = root / (PREFIX + name)
                path.write_bytes(data)
                if path.read_bytes() != data:
                    raise ValueError(f"written postimage differs: {name}")
            print("applied two scratch-only observer/fixture files")
        else:
            print("dry run; no files written")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"AI6 scratch preparation refused: {exc}\n")

if __name__ == "__main__":
    main()
