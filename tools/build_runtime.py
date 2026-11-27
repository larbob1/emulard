#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare and optionally compile a pinned, separate runtime checkout."""
import argparse
import os
import re
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

def apply_patch(path, target):
    # Windows can check out patch files as CRLF, while upstream enforces LF.
    # Normalize line endings only; retain exact context validation.
    print(f"Applying patch: {path.name}", flush=True)
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    subprocess.run(["git", "apply", "--check", "-"], cwd=target, input=payload, check=True)
    subprocess.run(["git", "apply", "-"], cwd=target, input=payload, check=True)

def build_binaries(target):
    run(["cargo", "build", "--locked", "--release", "-p", "victory"], target)
    run(["cargo", "build", "--locked", "--profile", "diag", "-p", "victory", "--features", "diagnostics"], target)

def test_result_counts(output):
    return [(int(passed), int(failed)) for passed, failed in
            re.findall(r"test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed;", output)]

def test_suite(target, package, suite, *, env=None, diagnostics=False, expected=None, ignored=False):
    command = ["cargo", "test", "--locked", "-p", package, "--lib"]
    if diagnostics:
        command.extend(["--features", "diagnostics"])
    command.append(suite)
    if ignored:
        if package != "victory-hle" or suite not in ("hle_pool_native_review::reentrant_pool_callback_progress", "hle_pool_gated_native_review::pending_start_and_idle_notification", "hle_pool_spawn_failure_review::spawn_panic_preserves_queued_work", "hle_delayed_native_review::delayed_queue_lifetime_and_termination") or expected != 1:
            raise ValueError("ignored HLE fixture requires exact count-one gate")
        command.extend(["--", "--ignored", "--test-threads=1"])
    print(f"Running runtime test: {package} {suite}", flush=True)
    switches = ("VICTORY_MAP_SKIP_SAME", "VICTORY_MAP_DIFF", "VICTORY_MAP_RUNS",
                "VICTORY_BACK_AVX2", "VICTORY_BACK_SPARSE_MERGE", "VICTORY_MAP_DIFF_RUNS", "VICTORY_TEXTURE_VIEW_ESTIMATE", "VICTORY_MAP_ALIAS_DIRECT", "VICTORY_MAP_EXACT_PLACEHOLDERS", "VICTORY_PIPELINE_COMPLETION_STRIPES")
    if env is not None:
        values = " ".join(f"{key}={env[key]}" for key in switches if env.get(key) in ("0", "1"))
        print("Runtime test switches: " + values, flush=True)
    try:
        result = subprocess.run(command, cwd=target, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors="replace",
                                **({"timeout": 600} if ignored else {}))
    except subprocess.TimeoutExpired:
        print(f"Runtime test watchdog expired: {package} {suite}", flush=True)
        raise subprocess.CalledProcessError(1, command)
    # Keep the compiler output available to local callers. CI filters this
    # output and never republishes source or title data.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    print(result.stdout, end="", flush=True)
    result.check_returncode()
    counts = test_result_counts(result.stdout)
    passed = sum(p for p, _ in counts)
    failed = sum(f for _, f in counts)
    if not counts or passed == 0 or failed:
        print(f"Runtime test matched no passing tests: {package} {suite}", flush=True)
        raise subprocess.CalledProcessError(1, command)
    if expected is not None and (len(counts) != 1 or passed != expected):
        print(f"Runtime test count mismatch: {package} {suite} expected={expected} passed={passed}", flush=True)
        raise subprocess.CalledProcessError(1, command)
    if ignored:
        ignored_counts = re.findall(r"test result: (?:ok|FAILED)\. \d+ passed; \d+ failed; (\d+) ignored;", result.stdout)
        if ignored_counts != ["0"]:
            raise subprocess.CalledProcessError(1, command)
    print(f"Runtime test counts: {package} {suite} passed={passed} failed={failed}", flush=True)

def validate_paired(target, *, keep_going=False):
    failures = []

    def attempt(label, action):
        try:
            action()
            print(f"Runtime validation passed: {label}", flush=True)
        except subprocess.CalledProcessError:
            if not keep_going:
                raise
            failures.append(label)
            print(f"Runtime validation failed: {label}", flush=True)

    def suite(package, name, *, env=None, diagnostics=False, expected=None, ignored=False):
        attempt(f"{package} {name}", lambda: test_suite(target, package, name, env=env, diagnostics=diagnostics, expected=expected, ignored=ignored))
    for mode in ("0", "1"):
        env = dict(os.environ, VICTORY_MAP_SKIP_SAME=mode, VICTORY_MAP_RUNS="0", VICTORY_MAP_DIFF="0")
        suite("victory-hle", "physical_pages_map_alias_and_unmap", env=env)
    for runs in ("0", "1"):
        env = dict(os.environ, VICTORY_MAP_SKIP_SAME="0", VICTORY_MAP_DIFF="1", VICTORY_MAP_RUNS=runs)
        suite("victory-hle", "physical_pages_map_alias_and_unmap", env=env)
        suite("victory-hle", "a_read_in_place_never_meets_the_gap_of_a_remapping", env=env)
    for mode in ("0", "1"):
        env = dict(os.environ, VICTORY_MAP_SKIP_SAME=mode, VICTORY_MAP_DIFF=mode, VICTORY_MAP_RUNS=mode)
        suite("victory-hle", "tile_replay_checks", env=env)
    suite("victory-hle", "perf6_worker_tests")
    suite("victory-hle", "xasync::tests::", expected=7)
    suite("victory-hle", "pool_callbacks_may_wait_for_each_other", expected=1)
    suite("victory-hle", "hle_pool_native_review::reentrant_pool_callback_progress", expected=1, ignored=True)
    suite("victory-hle", "hle_pool_gated_native_review::pending_start_and_idle_notification", expected=1, ignored=True)
    suite("victory-hle", "hle_pool_spawn_failure_review::spawn_panic_preserves_queued_work", expected=1, ignored=True)
    suite("victory-hle", "hle_delayed_native_review::delayed_queue_lifetime_and_termination", expected=1, ignored=True)
    suite("victory-gpu", "mapping_tests")
    suite("victory-gpu", "perf_hotpath_coverage_tests")
    env = dict(os.environ, VICTORY_MAP_SKIP_SAME="0", VICTORY_MAP_DIFF="1", VICTORY_MAP_RUNS="0", VICTORY_MAP_DIFF_RUNS="1")
    suite("victory-hle", "physical_pages_map_alias_and_unmap", env=env)
    suite("victory-hle", "tile_replay_checks", env=env)
    env = dict(os.environ, VICTORY_MAP_SKIP_SAME="0", VICTORY_MAP_DIFF="1", VICTORY_MAP_RUNS="1", VICTORY_MAP_DIFF_RUNS="1", VICTORY_MAP_ALIAS_DIRECT="1")
    suite("victory-hle", "physical_pages_map_alias_and_unmap", env=env)
    suite("victory-hle", "a_read_in_place_never_meets_the_gap_of_a_remapping", env=env)
    suite("victory-hle", "tile_replay_checks", env=env)
    suite("victory-gpu", "perf4_tests")
    for enabled in ("0", "1"):
        env = dict(os.environ, VICTORY_BACK_AVX2=enabled, VICTORY_BACK_SPARSE_MERGE=enabled)
        for name in ("difference_tests", "merge_tests"):
            suite("victory-gpu", name, env=env)
    for name in ("perf5_queue_tests", "draws_promote_early_pipelines_without_claiming_them_twice", "names_change_with_what_goes_into_the_pipeline", "translations_come_back_from_the_cache"):
        suite("victory-gpu", name)
    suite("victory-shader", "wave64_tests")
    suite("victory-gpu", "compositor", diagnostics=True)
    attempt("release build", lambda: run(["cargo", "build", "--locked", "--release", "-p", "victory"], target))
    attempt("diagnostics build", lambda: run(["cargo", "build", "--locked", "--profile", "diag", "-p", "victory", "--features", "diagnostics"], target))
    if failures:
        print(f"Runtime validation failed groups: {len(failures)}", flush=True)
        raise subprocess.CalledProcessError(1, ["paired-wave validation"])

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
        run(["git", "clone", "--no-checkout", "--config", "core.autocrlf=false", UPSTREAM, str(target)])
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
                apply_patch(own / "patches" / patch, target)
            run([sys.executable, str(PATCHER.with_name("apply_pipeline_stack_patch.py")), str(target), "--apply"])
            apply_patch(own / "patches" / "paired-wave-worker-tracing.patch", target)
            run([sys.executable, str(PATCHER.with_name("apply_mapping_fastpath.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_mapping_diff.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_texture_snapshot.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_gpu_copy_perf.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_pipeline_perf.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_disk_worker_perf.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_paired_tile_replay.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_checked_unmap.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_mapping_preflight.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_mapping_hotpath.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_alias_direct_run.py")), str(target)])
            run([sys.executable, str(PATCHER.with_name("apply_hle_pool_native.py")), str(target)])
            run(["git", "diff", "--check"], target)
            if ns.build:
                validate_paired(target)
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
                apply_patch(own / "patches" / patch, target)
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
        apply_patch(own / "patches" / "predicate-iterative.patch", target)
        run([sys.executable, str(PATCHER.with_name("apply_divergent_wave_retry_patch.py")), str(target), "--apply"])
        apply_patch(own / "patches" / "presentx-multiplane.patch", target)
        apply_patch(own / "patches" / "array-lod.patch", target)
        apply_patch(own / "patches" / "signature-interpolation.patch", target)
        apply_patch(own / "patches" / "indexed-buffer-descriptors.patch", target)
        # Belobug 8629211 and fxceless 8dd30ab, adapted to the pinned runtime.
        apply_patch(own / "patches" / "belobug-integer-blend.patch", target)
        apply_patch(own / "patches" / "fxceless-shared-exponent-target.patch", target)
        apply_patch(own / "patches" / "wine-disk-backed-memory.patch", target)
        apply_patch(own / "patches" / "wine-reuse-page-placeholders.patch", target)
        apply_patch(own / "patches" / "belobug-wave32-tiled-shadows.patch", target)
        apply_patch(own / "patches" / "pipeline-isolation.patch", target)
        apply_patch(own / "patches" / "pipeline-worker-tracing.patch", target)
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
