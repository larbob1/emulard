#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare and optionally compile a pinned, separate runtime checkout."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

UPSTREAM = "https://github.com/fxceless/victory-fork.git"
REVISION = "2119b0e44c53aa9648307b0c5c73590290305b1f"
PATCHER = Path(__file__).resolve().with_name("apply_memory_patch.py")

def run(args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkout", type=Path, help="new directory outside this repository")
    ap.add_argument("--build", action="store_true", help="compile using the Windows toolchain")
    ap.add_argument("--lighting-memory", action="store_true", help="apply the experimental shader page-boundary candidate")
    ns = ap.parse_args()
    target = ns.checkout.resolve()
    own = PATCHER.parent.parent
    if target.exists() or target == own or own in target.parents:
        ap.error("Select a new directory outside this repository.")
    if ns.build and os.name != "nt":
        ap.error("The reviewed runtime currently requires a Windows build host.")
    try:
        run(["git", "clone", "--no-checkout", UPSTREAM, str(target)])
        run(["git", "remote", "set-url", "--push", "origin", "DISABLED"], target)
        run(["git", "checkout", "--detach", REVISION], target)
        run([sys.executable, str(PATCHER), str(target), "--apply", "--scratch-budget", "--write-index"])
        run([sys.executable, str(PATCHER.with_name("apply_query_patch.py")), str(target), "--apply"])
        if ns.lighting_memory:
            run([sys.executable, str(PATCHER.with_name("apply_lighting_patch.py")), str(target), "--apply"])
            run([sys.executable, str(PATCHER.with_name("apply_fault_bitmap.py")), str(target), "--apply"])
        else:
            run([sys.executable, str(PATCHER.with_name("apply_lighting_patch.py")), str(target), "--apply", "--scalar-only"])
        run([sys.executable, str(PATCHER.with_name("apply_wave_patch.py")), str(target), "--apply"])
        run([sys.executable, str(PATCHER.with_name("apply_builder_patch.py")), str(target), "--apply"])
        dot = [sys.executable, str(PATCHER.with_name("apply_dot_patch.py")), str(target), "--apply"]
        if ns.lighting_memory:
            dot.append("--lighting-memory")
        run(dot, target)
        heap = [sys.executable, str(PATCHER.with_name("apply_heap_patch.py")), str(target), "--apply"]
        if ns.lighting_memory:
            heap.append("--lighting-memory")
        run(heap, target)
        run([sys.executable, str(PATCHER.with_name("apply_relative_patch.py")), str(target), "--apply"])
        run(["git", "diff", "--check"], target)
        if ns.build:
            if ns.lighting_memory:
                run(["cargo", "test", "--locked", "-p", "victory-gpu", "fault_bitmap_tests"], target)
                run(["cargo", "test", "--locked", "-p", "victory-gpu", "fault_recovery_batch_tests"], target)
                run(["cargo", "test", "--locked", "-p", "victory-gpu", "scoped_fault_bitmap_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "raw_copy_progress_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "directory_range_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "query_range_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "scratch_limit_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "write_index_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "wave_retry_policy_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "wave_cache_key_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "raw_scalar_base_global_access_lowers"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "packed_byte_dot_lowering"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "accumulating_byte_dot_lowering"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "accumulating_dot_reads_its_destination_as_an_operand"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "a_descriptor_of_numbers_is_title_memory_read_through_the_directory"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "packed_half_dot_lowering"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "local_relative_index_bounds_are_conservative"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "raw_compare_exchange_lowering"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "positive_mask_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "wave_tail_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "unpaired_host_wave_lowers_without_partner"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "snapshot_reservation_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "idle_snapshot_pool_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "snapshot_coverage_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "worker_limit_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "startup_worker_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "texture_budget_tests"], target)
            run(["cargo", "build", "--locked", "--release", "-p", "victory"], target)
            run(["cargo", "build", "--locked", "--profile", "diag", "-p", "victory", "--features", "diagnostics"], target)
        else:
            print("Patched source prepared; compilation not attempted.")
    except (OSError, subprocess.CalledProcessError) as exc:
        print("Preparation/build failed; inspect the local checkout and command output.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
