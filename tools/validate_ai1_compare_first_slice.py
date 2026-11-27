#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""AI1 isolated #82 validation. Never install or launch the runtime.

Prepare a disposable Windows checkout with the unmodified paired-wave builder.
Compare its shadow.rs against the independently reconstructed pinned postimage
before inserting an exact regression. The scratch checkout is discarded.
The arithmetic correction is from upstream PiloteCode #1407 / 81d54b0,
reviewed in AI0 #82. No production registration or default changes.
"""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from apply_gpu_copy_perf import transform
from build_runtime import PAIRED_WAVE_REFRESH

ROOT = Path(__file__).resolve().parent.parent
PATH = "crates/victory-gpu/src/shadow.rs"
RAW_BLOB = "4fa43df7932bb6692d164384cd28b1f08f3001ee"
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
OLD = "            (at - (start + at) % PIECE).max(from)"
NEW = "            at.saturating_sub((start + at) % PIECE).max(from)"
ANCHOR = "mod card_merge_tests {\n    use super::{Card, Shadow};"
NAME = "shadow::card_merge_tests::ai1_first_slice_exact_partition"
MARKER = "fn ai1_first_slice_exact_partition("
FIXTURE = """
    // AI1 title-free regression: real comparison, owned CPU vectors.
    // WARP is required; its resource is an unused owned handle in this test.
    #[test]
    fn ai1_first_slice_exact_partition() {
        const P: usize = 64 << 10;
        const M: usize = 1 << 20;
        let buffer = warp_buffer().expect("AI1 regression requires WARP");
        // The first case deliberately reproduces the original debug underflow.
        // Then cover serial, just below threshold, two/three/eight workers,
        // unaligned origins, nonzero from, and unchanged bytes.
        for (skew, from, len, change) in [
            (P / 2, 0, 32 * M, true),
            (P - 1, 1, 32 * M + 513, true),
            (17, P + 3, 48 * M + 17, true),
            (0, 17, 128 * M, true),
            (1, 0, 32 * M - 1, true),
            (P - 2, 1, 16 * M, true),
            (17, 5, 32 * M, false),
        ] {
            let start = (8 * P + skew) as u64;
            let to = from + len;
            let before = vec![0u8; len];
            let mut now = vec![0u8; to];
            let first_edge = ((start as usize + from) / P + 1) * P
                - start as usize;
            let changed = if change {
                vec![from, first_edge - 1, first_edge, from + len / 2, to - 1]
            } else {
                Vec::new()
            };
            let mut expected = Vec::new();
            for at in changed {
                now[at] = 0x5a;
                let page = (start as usize + at) / P;
                let a = (page * P).saturating_sub(start as usize).max(from);
                let b = ((page + 1) * P - start as usize).min(to);
                expected.push((a, b - a));
            }
            expected.sort_unstable();
            expected.dedup();
            let shadow = Shadow::new(buffer.clone(), now.as_mut_ptr(), 0, start, to as u64);
            assert_eq!(shadow.differing(from, to, &before), expected,
                "skew={skew}, from={from}, len={len}, change={change}");
            drop(shadow);
        }
    }
"""

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def normalized(data):
    if b"\r\n" in data and b"\n" in data.replace(b"\r\n", b""):
        raise ValueError("mixed source line endings")
    data = data.replace(b"\r\n", b"\n")
    if b"\r" in data:
        raise ValueError("unexpected CR")
    return data

def validated_preimage(raw, prepared):
    if blob(raw) != RAW_BLOB:
        raise ValueError("raw shadow blob mismatch")
    expected = transform(raw.decode("utf-8")).encode("utf-8")
    actual = normalized(prepared)
    if expected != actual:
        raise ValueError("prepared shadow differs from reconstructed postimage")
    return actual.decode("utf-8")

def fixture_source(source, fixed):
    if source.count(OLD) != 1 or source.count(ANCHOR) != 1 or MARKER in source:
        raise ValueError("source anchor mismatch")
    result = source.replace(ANCHOR, ANCHOR + "\n" + FIXTURE, 1)
    if fixed:
        result = result.replace(OLD, NEW, 1)
    return result

def write_source(path, source, original):
    if b"\r\n" in original:
        source = source.replace("\n", "\r\n")
    path.write_bytes(source.encode("utf-8"))

def receipt(output, code, *, baseline_line=None):
    baseline = baseline_line is not None
    status = "FAILED" if baseline else "ok"
    expected = f"test {NAME} ... {status}"
    test_lines = re.findall(r"^test \S+ \.\.\. (?:ok|FAILED|ignored.*)$", output, re.M)
    summaries = re.findall(
        r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; "
        r"(\d+) ignored; (\d+) measured; (\d+) filtered out;", output, re.M)
    if test_lines != [expected]:
        return False
    if len(summaries) != 1:
        return False
    want = ("FAILED", "0", "1", "0", "0") if baseline else ("ok", "1", "0", "0", "0")
    if summaries[0][:5] != want:
        return False
    site = rf"shadow\.rs:{baseline_line}:\d+" if baseline else None
    return (code != 0 and "attempt to subtract with overflow" in output
            and re.search(site, output) is not None if baseline else code == 0)

def run_exact(target, label, flags=(), *, baseline_line=None):
    baseline = baseline_line is not None
    command = ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib",
               *flags, NAME, "--", "--exact", "--test-threads=1"]
    env = dict(os.environ, VICTORY_BACK_AVX2="0", VICTORY_BACK_SPARSE_MERGE="0")
    result = subprocess.run(command, cwd=target, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors="replace",
                            timeout=3600)
    if not receipt(result.stdout, result.returncode, baseline_line=baseline_line):
        raise ValueError(f"{label}: missing or unexpected exact native receipt")
    print(f"{label}: {NAME}: " + ("expected overflow reproduced" if baseline else "1 passed; 0 failed"),
          flush=True)

def main():
    if os.name != "nt" or PAIRED_WAVE_REFRESH != UPSTREAM:
        print("INVALID: Windows and exact paired-wave revision required")
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="emulard-ai1-compare-") as tmp:
            target = Path(tmp) / "runtime"
            subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"),
                            str(target), "--paired-wave-refresh"], check=True)
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
            if revision != UPSTREAM:
                raise ValueError("upstream checkout mismatch")
            raw = subprocess.check_output(["git", "show", f"HEAD:{PATH}"], cwd=target)
            path = target / PATH
            original = path.read_bytes()
            source = validated_preimage(raw, original)
            print(f"upstream={revision} prepared_shadow_blob_lf={blob(source.encode())}", flush=True)
            baseline = fixture_source(source, False)
            write_source(path, baseline, original)
            baseline_line = baseline[:baseline.index(OLD)].count("\n") + 1
            run_exact(target, "Baseline debug", baseline_line=baseline_line)
            fixed = fixture_source(source, True)
            write_source(path, fixed, original)
            print(f"corrected_shadow_blob_lf={blob(fixed.encode())}", flush=True)
            subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
            run_exact(target, "Corrected debug")
            run_exact(target, "Corrected release", ("--release",))
            run_exact(target, "Corrected diagnostics", ("--features", "diagnostics"))
            subprocess.run([sys.executable, str(ROOT / "tools/ci_paired_tests.py"), str(target)], check=True)
            print("Isolated native regression and paired-wave gates passed; no gameplay acceptance", flush=True)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Validation failed: {type(exc).__name__}", flush=True)
        if isinstance(exc, ValueError):
            print(str(exc), flush=True)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
