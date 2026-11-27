#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile a source-only candidate on a Windows CI host."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent

def run_stage(label, args, cwd):
    # Do not publish external source excerpts, local paths or raw tool logs.
    # Report only a stage name, exit status, and structured Rust error codes.
    print(f"Starting: {label}", flush=True)
    with tempfile.TemporaryFile(mode="w+b") as output:
        result = subprocess.run(args, cwd=cwd, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            output.seek(0)
            codes = set()
            preparation = set()
            unresolved = set()
            locations = set()
            patches = set()
            last_patch = None
            patch_locations = set()
            categories = set()
            last_test = None
            empty_tests = set()
            for line in output:
                test = re.fullmatch(rb"Running runtime test: (victory-[a-z-]+ [A-Za-z0-9_]+)\s*", line)
                if test:
                    last_test = test[1].decode("ascii")
                empty = re.fullmatch(rb"Runtime test matched no passing tests: (victory-[a-z-]+ [A-Za-z0-9_]+)\s*", line)
                if empty:
                    empty_tests.add(empty[1].decode("ascii"))
                codes.update(re.findall(rb"error\[(E[0-9]{4})\]", line))
                if b"error[E0425]" in line:
                    unresolved.update(re.findall(rb"\x60([A-Za-z_][A-Za-z_0-9]*)\x60", line))
                location = re.search(rb"--> (crates[\\/][A-Za-z0-9_-]+[\\/]src[\\/][A-Za-z0-9_\\/.-]+\.rs):([0-9]+):([0-9]+)", line)
                if location:
                    locations.add(b":".join(location.groups()).replace(b"\\", b"/"))
                if label == "Pinned source preparation":
                    applied = re.fullmatch(rb"Applying patch: ([a-z0-9][a-z0-9-]+\.patch)\s*", line)
                    if applied:
                        last_patch = applied[1].decode("ascii")
                    failed = re.search(rb"patch failed: ((?:crates|apps)/[A-Za-z0-9_./-]+\.rs):([0-9]+)", line)
                    if failed:
                        patch_locations.add(b":".join(failed.groups()).decode("ascii"))
                    for name in re.findall(rb"apply_[a-z_]+\.py", line):
                        preparation.add(name.decode("ascii"))
                    for name in re.findall(rb"[a-z0-9][a-z0-9-]+\.patch", line):
                        patches.add(name.decode("ascii"))
                    for phrase, category in (
                        (b"patch does not apply", "patch context mismatch"),
                        (b"patch failed", "patch context mismatch"),
                        (b"source anchor", "source anchor mismatch"),
                        (b"could not resolve host", "network DNS failure"),
                        (b"could not read username", "authentication unavailable"),
                        (b"repository not found", "upstream repository unavailable"),
                        (b"failed to connect", "network connection failure"),
                        (b"unable to access", "upstream access failure"),
                        (b"trailing whitespace", "patch whitespace failure"),
                    ):
                        if phrase in line.lower():
                            categories.add(category)
            if last_test:
                print("Last runtime suite attempted: " + last_test)
            if empty_tests:
                print("Empty runtime suites: " + ", ".join(sorted(empty_tests)))
            if last_patch:
                print("Last patch attempted: " + last_patch)
            if patch_locations:
                print("Patch context locations: " + ", ".join(sorted(patch_locations)))
            if categories:
                print("Preparation failure categories: " + ", ".join(sorted(categories)))
            if patches:
                print("Patch names mentioned: " + ", ".join(sorted(patches)))
            if preparation:
                print("Preparation scripts mentioned: " + ", ".join(sorted(preparation)))
            if unresolved:
                print("Unresolved identifiers: " + ", ".join(x.decode("ascii") for x in sorted(unresolved)))
            if locations:
                print("Diagnostic locations: " + ", ".join(x.decode("ascii") for x in sorted(locations)))
            if codes:
                print("Rust diagnostics: " + ", ".join(code.decode("ascii") for code in sorted(codes)))
            print(f"Failed: {label} (exit {result.returncode})", flush=True)
            raise SystemExit(1)
    print(f"Passed: {label}", flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--lighting-memory", action="store_true")
    mode.add_argument("--paired-wave-refresh", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Windows build host required.")
    try:
        with tempfile.TemporaryDirectory(prefix="emulard-ci-") as directory:
            target = Path(directory) / "runtime"
            run_stage(
                "Pipeline worker stack patch",
                [sys.executable, "test_apply_pipeline_stack_patch.py"],
                ROOT / "tools",
            )
            prepare = [sys.executable, str(ROOT / "tools" / "build_runtime.py"), str(target)]
            if args.paired_wave_refresh:
                run_stage("Pinned source preparation", prepare + ["--paired-wave-refresh"], ROOT)
                run_stage("Pinned Rust toolchain", ["cargo", "--version"], target)
                run_stage("Paired-wave tests and release/diag compilation",
                          [sys.executable, str(ROOT / "tools" / "ci_paired_tests.py"), str(target)], ROOT)
                print("Paired-wave compile and test checks completed. No gameplay execution was attempted.", flush=True)
                return 0
            if args.lighting_memory:
                prepare.append("--lighting-memory")
            run_stage("Pinned source preparation", prepare, ROOT)
            run_stage("Pinned Rust toolchain", ["rustup", "toolchain", "install"], target)
            suites = [
                ("Memory scheduling", "victory-gpu", "raw_copy_progress_tests"),
                ("Raw directory bounds", "victory-gpu", "directory_range_tests"),
                ("Query bounds", "victory-gpu", "query_range_tests"),
                ("Idle upload pool", "victory-gpu", "scratch_limit_tests"),
                ("Write declaration index", "victory-gpu", "write_index_tests"),
                ("Pipeline worker cap", "victory-gpu", "worker_limit_tests"),
                ("Startup compiler memory cap", "victory-gpu", "startup_worker_tests"),
                ("Texture budget", "victory-gpu", "texture_budget_tests"),
                ("Wave retry policy", "victory-shader", "wave_retry_policy_tests"),
                ("Host wave cache key", "victory-gpu", "wave_cache_key_tests"),
                ("Raw scalar-base addressing", "victory-shader", "raw_scalar_base_global_access_lowers"),
                ("Packed-byte dot lowering", "victory-shader", "packed_byte_dot_lowering"),
                ("Signed wide multiply-add result", "victory-shader", "signed_mad_result_lowering"),
                ("Accumulating byte dot lowering", "victory-shader", "accumulating_byte_dot_lowering"),
                ("Accumulator operand tracking", "victory-shader", "accumulating_dot_reads_its_destination_as_an_operand"),
                ("Ray directory translation", "victory-shader", "a_descriptor_of_numbers_is_title_memory_read_through_the_directory"),
                ("Packed-half dot lowering", "victory-shader", "packed_half_dot_lowering"),
                ("Relative index bounds", "victory-shader", "local_relative_index_bounds_are_conservative"),
                ("Global compare exchange", "victory-shader", "raw_compare_exchange_lowering"),
                ("Positive wave mask proof", "victory-shader", "positive_mask_tests"),
                ("Wave tail layout", "victory-shader", "wave_tail_tests"),
                ("Unpaired host wave lowering", "victory-shader", "unpaired_host_wave_lowers_without_partner"),
                ("Split-wave backward permute", "victory-shader", "split_wave_backward_permute_lowers"),
                ("Snapshot budget reservation", "victory-gpu", "snapshot_reservation_tests"),
                ("Idle snapshot pool limit", "victory-gpu", "idle_snapshot_pool_tests"),
                ("Snapshot coverage and retirement", "victory-gpu", "snapshot_coverage_tests"),
                ("Ray intersection reference", "victory-shader", "bvh::tests::"),
            ]
            if args.lighting_memory:
                suites.append(("Fault bitmap decoding", "victory-gpu", "fault_bitmap_tests"))
                suites.append(("Fault recovery batch", "victory-gpu", "fault_recovery_batch_tests"))
                suites.append(("Transient mapping retry", "victory-gpu", "mapping_retry_tests"))
                suites.append(("Scoped feedback completion", "victory-gpu", "scoped_fault_bitmap_tests"))
            for label, package, name in suites:
                run_stage(label, ["cargo", "test", "--locked", "-p", package, "--lib", name], target)
            run_stage("Release runtime compilation", ["cargo", "build", "--locked", "--release", "-p", "victory"], target)
            run_stage("Diagnostics type check", ["cargo", "check", "--locked", "-p", "victory", "--features", "diagnostics"], target)
            print("Compile and targeted test checks completed. No runtime execution was attempted.", flush=True)
    except OSError:
        print("CI preparation or cleanup failed.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
