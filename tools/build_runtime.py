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
FXCELESS_REFRESH = "d510ee4a9b635bcc345207a73ccb4c4fceb8228c"
PAIRED_WAVE_REFRESH = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
PATCHER = Path(__file__).resolve().with_name("apply_memory_patch.py")

def run(args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)

def build_binaries(target):
    run(["cargo", "build", "--locked", "--release", "-p", "victory"], target)
    run(["cargo", "build", "--locked", "--profile", "diag", "-p", "victory", "--features", "diagnostics"], target)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkout", type=Path, help="new directory outside this repository")
    ap.add_argument("--build", action="store_true", help="compile using the Windows toolchain")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--lighting-memory", action="store_true", help="apply the experimental shader page-boundary candidate")
    mode.add_argument("--fxceless-refresh", action="store_true", help="use the newer fxceless renderer with the integer blend and Wine memory fixes")
    mode.add_argument("--paired-wave-refresh", action="store_true", help="use the paired-wave shader translator from fxceless PR #854")
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
        if ns.paired_wave_refresh:
            run(["git", "fetch", "--no-tags", "origin", PAIRED_WAVE_REFRESH], target)
            run(["git", "checkout", "--detach", PAIRED_WAVE_REFRESH], target)
            for patch in (
                "belobug-integer-blend-fxceless.patch",
                "wine-disk-backed-memory.patch",
                "paired-wave-presentx.patch",
                "paired-wave-accc.patch",
                "paired-wave-loop-latches.patch",
                "paired-wave-map-runs.patch",
                "paired-wave-placed-uav.patch",
                "paired-wave-present-capture.patch",
                "paired-wave-graphics-priority.patch",
                "paired-wave-dropped-scene-draws.patch",
                "paired-wave-native-upscaler.patch",
                "paired-wave-remap-timing.patch",
                "paired-wave-wine-placeholder-reuse.patch",
            ):
                run(["git", "apply", str(own / "patches" / patch)], target)
            run([sys.executable, str(PATCHER.with_name("apply_pipeline_stack_patch.py")), str(target), "--apply"])
            run(["git", "apply", str(own / "patches" / "paired-wave-worker-tracing.patch")], target)
            run([sys.executable, str(PATCHER.with_name("apply_mapping_fastpath.py")), str(target)])
            run(["git", "diff", "--check"], target)
            if ns.build:
                for mode in ("0", "1"):
                    env = dict(os.environ, VICTORY_MAP_SKIP_SAME=mode, VICTORY_MAP_RUNS="0")
                    subprocess.run(["cargo", "test", "--locked", "-p", "victory-hle", "physical_pages_map_alias_and_unmap"], cwd=target, env=env, check=True)
                run(["cargo", "test", "--locked", "-p", "victory-shader", "wave64_tests"], target)
                run(["cargo", "test", "--locked", "-p", "victory-gpu", "--features", "diagnostics", "compositor"], target)
                build_binaries(target)
            else:
                print("Patched source prepared; compilation not attempted.")
            return 0
        revision = FXCELESS_REFRESH if ns.fxceless_refresh else REVISION
        run(["git", "checkout", "--detach", revision], target)
        if ns.fxceless_refresh:
            for patch in (
                "belobug-integer-blend-fxceless.patch",
                "wine-disk-backed-memory.patch",
                "reuse-page-placeholder.patch",
                "streaming-page-aliases.patch",
                "tile-mapping-replay.patch",
                "texture-table-check.patch",
                "render-target-bind-cache.patch",
                "wave-wide-digest-selection.patch",
                "belobug-wave32-tiled-shadows.patch",
                "texture-view-coverage.patch",
                "reuse-vacant-page-placeholders.patch",
            ):
                run(["git", "apply", str(own / "patches" / patch)], target)
            run(["git", "diff", "--check"], target)
            if ns.build:
                run(["cargo", "test", "--locked", "-p", "victory-hle", "tile_replay_checks"], target)
                run(["cargo", "test", "--locked", "-p", "victory-hle", "vacant_pages_can_be_remapped_after_coalescing"], target)
                build_binaries(target)
            else:
                print("Patched source prepared; compilation not attempted.")
            return 0
        run([sys.executable, str(PATCHER), str(target), "--apply", "--scratch-budget", "--write-index"])
        run([sys.executable, str(PATCHER.with_name("apply_query_patch.py")), str(target), "--apply"])
        if ns.lighting_memory:
            run([sys.executable, str(PATCHER.with_name("apply_lighting_patch.py")), str(target), "--apply"])
            run([sys.executable, str(PATCHER.with_name("apply_fault_bitmap.py")), str(target), "--apply"])
        else:
            run([sys.executable, str(PATCHER.with_name("apply_lighting_patch.py")), str(target), "--apply", "--scalar-only"])
        run([sys.executable, str(PATCHER.with_name("apply_wave_patch.py")), str(target), "--apply"])
        run([sys.executable, str(PATCHER.with_name("apply_builder_patch.py")), str(target), "--apply"])
        run([sys.executable, str(PATCHER.with_name("apply_pipeline_stack_patch.py")), str(target), "--apply"])
        dot = [sys.executable, str(PATCHER.with_name("apply_dot_patch.py")), str(target), "--apply"]
        if ns.lighting_memory:
            dot.append("--lighting-memory")
        run(dot, target)
        heap = [sys.executable, str(PATCHER.with_name("apply_heap_patch.py")), str(target), "--apply"]
        if ns.lighting_memory:
            heap.append("--lighting-memory")
        run(heap, target)
        run([sys.executable, str(PATCHER.with_name("apply_relative_patch.py")), str(target), "--apply"])
        run([sys.executable, str(PATCHER.with_name("apply_iterative_bool_patch.py")), str(target), "--apply"])
        run(["git", "apply", str(own / "patches" / "predicate-iterative.patch")], target)
        run([sys.executable, str(PATCHER.with_name("apply_divergent_wave_retry_patch.py")), str(target), "--apply"])
        run(["git", "apply", str(own / "patches" / "presentx-multiplane.patch")], target)
        run(["git", "apply", str(own / "patches" / "array-lod.patch")], target)
        run(["git", "apply", str(own / "patches" / "signature-interpolation.patch")], target)
        run(["git", "apply", str(own / "patches" / "indexed-buffer-descriptors.patch")], target)
        # Belobug 8629211 and fxceless 8dd30ab, adapted to the pinned runtime.
        run(["git", "apply", str(own / "patches" / "belobug-integer-blend.patch")], target)
        run(["git", "apply", str(own / "patches" / "fxceless-shared-exponent-target.patch")], target)
        run(["git", "apply", str(own / "patches" / "wine-disk-backed-memory.patch")], target)
        run(["git", "apply", str(own / "patches" / "wine-reuse-page-placeholders.patch")], target)
        run(["git", "apply", str(own / "patches" / "belobug-wave32-tiled-shadows.patch")], target)
        run(["git", "apply", str(own / "patches" / "pipeline-isolation.patch")], target)
        run(["git", "apply", str(own / "patches" / "pipeline-worker-tracing.patch")], target)
        run(["git", "diff", "--check"], target)
        if ns.build:
            if ns.lighting_memory:
                run(["cargo", "test", "--locked", "-p", "victory-gpu", "fault_bitmap_tests"], target)
                run(["cargo", "test", "--locked", "-p", "victory-gpu", "fault_recovery_batch_tests"], target)
                run(["cargo", "test", "--locked", "-p", "victory-gpu", "mapping_retry_tests"], target)
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
            run(["cargo", "test", "--locked", "-p", "victory-shader", "signed_mad_result_lowering"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "accumulating_byte_dot_lowering"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "accumulating_dot_reads_its_destination_as_an_operand"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "a_descriptor_of_numbers_is_title_memory_read_through_the_directory"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "packed_half_dot_lowering"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "local_relative_index_bounds_are_conservative"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "raw_compare_exchange_lowering"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "positive_mask_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "wave_tail_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "unpaired_host_wave_lowers_without_partner"], target)
            run(["cargo", "test", "--locked", "-p", "victory-shader", "split_wave_backward_permute_lowers"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "snapshot_reservation_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "idle_snapshot_pool_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "snapshot_coverage_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "worker_limit_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "startup_worker_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "texture_budget_tests"], target)
            run(["cargo", "test", "--locked", "-p", "victory-gpu", "integer_blend_tests"], target)
            build_binaries(target)
        else:
            print("Patched source prepared; compilation not attempted.")
    except (OSError, subprocess.CalledProcessError) as exc:
        print("Preparation/build failed; inspect the local checkout and command output.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
