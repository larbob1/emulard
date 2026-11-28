# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated checked texture preview native gate; no production registration."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)

def build(target, release):
    args = ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib", "--features",
            "diagnostics", "--no-run", "--message-format=json"]
    if release:
        args.append("--release")
    try:
        r = subprocess.run(args, cwd=target, capture_output=True, text=True,
                           errors="replace", timeout=2400, env=clean_env())
    except subprocess.TimeoutExpired as exc:
        for label, stream in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            print(label + " (partial compile):", flush=True)
            if stream:
                print(stream.decode("utf-8", errors="replace") if isinstance(stream, bytes) else stream, flush=True)
        raise
    if r.returncode:
        print((r.stdout + "\n" + r.stderr)[-20000:], flush=True)
        raise ValueError("test compile failed")
    artifacts = []
    for line in r.stdout.splitlines():
        obj = json.loads(line)
        if (obj.get("reason") == "compiler-artifact" and obj.get("executable")
                and obj.get("target", {}).get("name") == "victory_gpu"
                and obj.get("profile", {}).get("test") is True):
            artifacts.append(Path(obj["executable"]).resolve())
    if len(artifacts) != 1 or not artifacts[0].is_file() or not artifacts[0].is_relative_to(target.resolve()):
        raise ValueError(f"unexpected test executables: {artifacts}")
    return artifacts[0]

REVIEWED = "bc78a402cf8dee2de17ba117de44495013e4aad9"
PREPARER = "tools/prepare_ai2_checked_texture_preview_native.py"
PINS = {
    PREPARER: "d2eb4c2b5f070b006e1bc8149e48d000adb0b4d7",
    "tools/prepare_ai2_checked_texture_preview.py": "4cb69cac1d6387f18a91863c7bcfbcdc759dc932",
    "probes/ai2_checked_texture_preview_native.rs": "9f5206dd7db04be3022637b32288e4a6b30a8482",
    "probes/ai2_texback_record_resource.rs": "80250d2d44288ba0d708f39c4ed674aec6bc5d30",
    "patches/ai2-checked-texture-preview-common-r2.patch": "57431b71dc138f7f82c82ea97dd60977530ffeda",
    "patches/ai2-checked-texture-preview.patch": "b007b798e789a766b4293ea9643fe259f1e6e02d",
    "docs/ai2-checked-texture-preview-native.md": "9e0f8bff9db8e97b0e7efc07d6d36addc0eca4e6",
    "tools/build_runtime.py": BUILDER,
}
POST = {
    "crates/victory-gpu/src/host.rs": "031a65c12bbab967759383b2a75a3be46c46bbde",
    "crates/victory-gpu/src/texback.rs": "3eeedd9fcf5b758e81c9c04daea04d01c2b50932",
    "crates/victory-gpu/src/resource.rs": "314c10076c9fa7f07a8fb24f69b4c44f3b758185",
}
CASES = ("Replay", "Refusal")
NAMES = tuple("texback::checked_preview::ai2_preview_native::actual_preview_" + suffix
              for suffix in ("replay", "refusal"))
# Historical exact #148 job 140870402484 discovery, replacing only its four
# fixture tests with the two reviewed A tests. Any other drift is a failure.
EXPECTED_FULL = frozenset([
    "capture::tests::crc_matches_the_png_check_value: test",
    "capture::tests::unorm16_and_xr_bias_targets_decode_as_their_formats: test",
    "cardmeter::tests::a_list_is_named_by_the_pipelines_it_binds: test",
    "cardmeter::tests::a_pairs_length_is_in_microseconds_of_the_queues_clock: test",
    "copystat::command_tests::commands_are_named_by_their_pipeline: test",
    "copystat::own_tests::a_block_is_counted_while_it_lives: test",
    "copystat::own_tests::big_blocks_are_listed_while_they_live: test",
    "copystat::own_tests::blocks_count_in_their_size_class: test",
    "descriptor::host::own_copy_tests::a_view_off_its_copys_elements_gets_its_own_bytes: test",
    "descriptor::host::own_copy_tests::placed_unordered_texture_view_mirrors_and_aliases_to_shader_view: test",
    "descriptor::host::record_print_tests::a_record_that_changed_prints_otherwise: test",
    "descriptor::host::tests::a_newer_view_of_other_memory_makes_the_older_stale: test",
    "descriptor::host::tests::a_page_write_makes_an_uploaded_texture_slot_due_when_asked: test",
    "descriptor::host::tests::a_slot_rewritten_moves_to_its_new_span: test",
    "descriptor::host::tests::a_structured_view_made_raw_passes_the_host_check: test",
    "descriptor::host::tests::a_texture_written_at_the_start_of_another_replaces_it: test",
    "descriptor::host::tests::a_write_at_the_start_of_a_packed_texture_names_it_alone: test",
    "descriptor::host::tests::dynamic_slots_are_held_until_released: test",
    "descriptor::host::tests::memory_changed_under_packed_neighbours_names_the_ones_there: test",
    "descriptor::host::tests::never_stale_leaves_overlapping_views_out: test",
    "descriptor::host::tests::null_3d_uav_is_accepted_by_the_device: test",
    "descriptor::host::tests::null_uavs_keep_the_titles_dimension: test",
    "descriptor::host::tests::packed_neighbours_stay: test",
    "descriptor::host::tests::remapped_memory_makes_its_texture_slots_due: test",
    "descriptor::host::tests::slots_held_for_lack_of_room_come_back_when_there_is_room: test",
    "descriptor::host::tests::slots_read_through_tables_leave_the_texture_queue: test",
    "descriptor::host::tests::spans_say_the_next_start_and_the_lowest_level_viewed: test",
    "descriptor::host::tests::the_texture_queue_serves_the_newest_writes_first: test",
    "descriptor::host::tests::views_of_one_placed_texture_are_told_by_address_and_description: test",
    "descriptor::tests::constant_views_fit_their_records: test",
    "descriptor::tests::heaps_hold_count_descriptors_from_their_start: test",
    "descriptor::tests::placed_heaps_start_at_the_title_memory: test",
    "descriptor::tests::raw_heap_sync_stops_before_dynamic_host_slots: test",
    "descriptor::tests::records_copied_as_bytes_are_made_at_the_next_sync: test",
    "descriptor::tests::views_at_new_addresses_add_no_entries: test",
    "descriptor::tests::views_die_with_their_resource: test",
    "descriptor::tests::views_survive_copies: test",
    "device::tests::creation_hands_out_the_device: test",
    "device::tests::feature_levels_pick_the_highest_supported: test",
    "device::tests::newer_device_levels_are_the_same_device: test",
    "device::tests::the_device_is_found_at_every_level_through_others: test",
    "device::tests::the_hosts_children_hand_out_newer_device_levels: test",
    "device::tests::virtual_memory_configuration_reports_user_space: test",
    "draw::tests::a_lone_record_opens_a_window_at_the_remembered_step: test",
    "drvwatch::tests::an_entry_written_reaches_a_subscription: test",
    "drvwatch::tests::the_first_error_trips_the_switch_and_every_one_is_counted: test",
    "drvwatch::tests::the_system_takes_the_subscription: test",
    "dxgi::tests::startup_walks_from_device_to_output: test",
    "fence::tests::signals_set_waiting_events: test",
    "fpsbox::tests::pixels_are_in_the_formats_the_layer_presents_in: test",
    "fpsbox::tests::the_box_holds_every_glyph_with_a_margin: test",
    "fpsbox::tests::the_text_is_the_rate_to_a_tenth: test",
    "frame::tests::waits_end_on_ticks_and_count_frames: test",
    "framelog::tests::a_long_frame_is_listed_beside_the_usual_one: test",
    "framelog::tests::long_is_half_as_long_again_and_at_least_40_ms_more: test",
    "framelog::tests::more_long_frames_than_are_listed_are_counted: test",
    "framelog::tests::totals_and_a_threads_own_counts_add_up: test",
    "host::batch::a_texture_is_checked_once_per_submission: test",
    "host::batch::ram_idle_ms_scales_with_pressure: test",
    "host::batch::texture_checks_per_submission: test",
    "host::batch::title_writes_make_textures_due_again: test",
    "host::batch::vram_idle_ms_scales_with_pressure: test",
    "host::late_tests::copies_join_only_end_to_end_and_apart: test",
    "host::late_tests::ranges_touch_where_they_overlap: test",
    "host::present_plane_tests::compositor_failure_preserves_single_plane_presentation: test",
    "host::queue2_tests::warp_a_piece_fetched_while_a_later_flight_writes_it_is_fetched_again: test",
    "host::queue2_tests::warp_title_bytes_go_up_and_shader_writes_come_back_whatever_the_queues: test",
    "host::relay_tests::a_piece_fetched_beside_a_later_flight_is_fetched_again_by_it: test",
    "host::relay_tests::a_piece_flagged_under_one_range_is_fetched_under_all: test",
    "host::relay_tests::flights_land_in_the_order_they_were_sent: test",
    "host::spare::kept_things_come_back_by_size_within_the_limit: test",
    "host::tests::present_compositor_builds_both_pipeline_states: test",
    "host::tests::sparse_copies_preserve_islands_and_observe_remaps: test",
    "host::tests::warp_adapter_accepts_only_software: test",
    "host::trail::the_removal_report_says_the_newest_things_done: test",
    "indirect::bare_cost::bare_command_cost: test",
    "indirect::bench::bench_indirect_draw_barriers: test",
    "indirect::tests::argument_clamp_builds: test",
    "indirect::tests::gathered_records_must_fit_the_clamp: test",
    "indirect::tests::host_list_budget_starts_empty_at_each_submission: test",
    "indirect::tests::host_list_reuses_and_grows_scratch_across_submissions: test",
    "indirect::tests::host_list_window_check_finds_a_record_written_under_its_window: test",
    "indirect::tests::host_list_window_executions_need_no_barrier_of_their_own: test",
    "indirect::tests::rejects_unaligned_or_undersized_layouts: test",
    "indirect::tests::warp_a_group_charges_its_records_in_lane_order: test",
    "indirect::tests::warp_budget_saturates_without_wraparound_and_preserves_draw_fields: test",
    "indirect::tests::warp_card_compare_stores_the_hash_it_made_when_told: test",
    "indirect::tests::warp_card_fetch_copies_flagged_pieces_to_their_slots: test",
    "indirect::tests::warp_count_buffer_ignores_garbage_tail_and_preserves_source: test",
    "indirect::tests::warp_gathered_records_come_out_as_if_clamped_one_by_one: test",
    "indirect::tests::warp_window_executions_read_their_records_with_no_barrier_between: test",
    "indirect::tests::warp_window_leaves_unfilled_slots_empty_and_uncharged: test",
    "inplace::perf_hotpath_coverage_tests::agrees_with_existing_cover_for_valid_view_tables: test",
    "inplace::perf_hotpath_coverage_tests::handles_contiguous_scattered_holes_and_boundaries: test",
    "inplace::tests::census_tells_private_memory_from_views: test",
    "inplace::tests::only_private_memory_committed_whole_is_a_part: test",
    "inplace::tests::remapped_memory_forgets_its_views: test",
    "inplace::tests::views_say_what_one_placed_buffer_could_show: test",
    "inplace::tests::warp_a_title_buffer_in_place_shows_its_bytes_at_its_offset: test",
    "inplace::tests::warp_probe_opens_title_like_memory_and_the_gpu_sees_its_bytes: test",
    "list::tests::every_inline_command_falls_back_to_the_table: test",
    "object::tests::guids_round_trip_through_text: test",
    "pipeline::host::tests::a_mesh_pipeline_loads_from_the_library: test",
    "pipeline::host::tests::depth_bounds_pipeline_loads_and_filters_draws: test",
    "pipeline::library::tests::a_rejected_blob_gives_an_empty_library: test",
    "pipeline::library::tests::a_replaced_library_file_still_reads_from_the_disk: test",
    "pipeline::library::tests::names_change_with_what_goes_into_the_pipeline: test",
    "pipeline::library::tests::the_library_file_is_mapped_and_replaced: test",
    "pipeline::make::perf5_queue_tests::bounded_burst_yields_to_requested_other_work: test",
    "pipeline::make::perf5_queue_tests::bounded_worker_settings: test",
    "pipeline::make::tests::draws_promote_early_pipelines_without_claiming_them_twice: test",
    "pipeline::make::tests::first_use_is_made_by_a_worker: test",
    "pipeline::make::tests::pending_pipeline_is_recorded_for_the_next_launch: test",
    "pipeline::tests::pipelines_keep_their_shaders: test",
    "pipeline::tests::skip_hashes_accepts_full_hashes_only: test",
    "pipeline::tests::streams_yield_their_shaders: test",
    "plaincopy::tests::a_page_that_is_not_there_ends_the_copy_without_a_fault: test",
    "plaincopy::tests::a_source_that_faulted_is_remembered_by_its_blocks: test",
    "plaincopy::tests::memory_that_is_there_is_copied: test",
    "plaincopy::tests::threads_fault_and_copy_side_by_side: test",
    "primitive::tests::elements_past_the_stride_are_left_alone: test",
    "primitive::tests::half_subnormals_convert_in_both_directions: test",
    "primitive::tests::halves_round_up_into_the_next_power_of_two: test",
    "primitive::tests::rectangles_get_their_fourth_corner: test",
    "profile::tests::a_tree_keeps_each_call_site_once: test",
    "profile::tests::deep_stacks_are_cut_not_lost: test",
    "profile::tests::names_say_what_waits_and_whose_code_it_is: test",
    "profile::tests::stacks_that_mean_nothing_are_walked_without_a_fault: test",
    "profile::tests::the_sampler_finds_threads_and_writes_its_files: test",
    "profile::tests::the_walk_in_the_copy_is_the_systems_walk: test",
    "profile::tests::threads_are_followed_by_what_they_were_seen_doing: test",
    "profile::tests::time_goes_to_the_function_that_spent_it: test",
    "profile::tests::times_are_classed_four_to_a_power_of_two: test",
    "profile::tests::what_looking_costs: test",
    "queue2::tests::a_landing_buffer_is_free_when_the_card_has_passed_its_use: test",
    "queue2::tests::a_lanes_busy_time_counts_each_moment_once: test",
    "queue2::tests::warp_a_fetch_behind_a_fence_holds_everything_sent_before_that_fence: test",
    "queue2::tests::warp_a_fetch_through_the_copy_queue_brings_what_the_direct_queue_brings: test",
    "queue2::tests::warp_a_lanes_lists_are_used_again_only_after_their_job: test",
    "queue2::tests::warp_the_direct_queue_goes_on_only_when_what_was_sent_up_is_there: test",
    "queue2::tests::warp_title_bytes_reach_the_copy_through_a_landing_buffer_in_the_direct_queues_order: test",
    "queue::tests::console_queues_are_created_as_on_pc: test",
    "queue::tests::joined_parts_keep_their_lists_and_their_order: test",
    "queue::tests::newer_queues_have_their_methods_two_slots_later: test",
    "queue::tests::queue_signals_complete_at_once: test",
    "queue::tests::timestamps_and_values_are_written: test",
    "resource::tests::a_depth_planes_twin_is_drawn_into_the_plane: test",
    "resource::tests::a_depth_texture_and_its_twin_copy_into_each_other: test",
    "resource::tests::a_stencil_planes_twin_reaches_the_plane: test",
    "resource::tests::buffer_data_reaches_the_host_texture: test",
    "resource::tests::cached_placed_uav_is_visible_after_releasing_a_temporary_target: test",
    "resource::tests::committed_and_placed_resources_map_at_their_gpu_address: test",
    "resource::tests::device_setup_heap_properties_and_resources_at_addresses: test",
    "resource::tests::heaps_are_zeroed_aligned_memory: test",
    "resource::tests::sizes_cover_every_mip: test",
    "resource::tests::upload_footprints_follow_the_pc_rules: test",
    "root::tests::host_serialized_blobs_create_root_signatures: test",
    "root::tests::our_blobs_deserialize_on_the_host: test",
    "root::tests::versioned_descriptions_serialize_on_the_host: test",
    "sampler::tests::console_descriptions_decode: test",
    "shader_cache::tests::entries_round_trip_and_reject_damage: test",
    "shader_cache::tests::translations_come_back_from_the_cache: test",
    "shadow::card_merge_tests::a_title_byte_sent_after_a_flight_survives_its_slot: test",
    "shadow::card_tests::a_fetch_the_old_way_keeps_the_notes_flights_in_the_air_need: test",
    "shadow::card_tests::a_piece_fetched_in_flight_fits_its_slot: test",
    "shadow::card_tests::inflight_slots_are_a_power_of_two: test",
    "shadow::card_tests::inflight_tickets_never_share_a_slot_across_the_wrap: test",
    "shadow::card_tests::piece_runs_join_without_losing_or_adding_pieces: test",
    "shadow::card_tests::ranges_join_where_they_touch: test",
    "shadow::card_tests::the_shader_and_the_merge_cut_the_same_pieces: test",
    "shadow::difference_tests::differences_are_found_as_byte_by_byte: test",
    "shadow::difference_tests::differences_ignore_bytes_past_the_shorter_slice: test",
    "shadow::merge_tests::a_byte_both_changed_keeps_the_titles_and_only_gpu_bytes_are_written: test",
    "shadow::merge_tests::a_piece_put_back_reads_only_its_stretch: test",
    "shadow::merge_tests::changed_chunks_hold_every_changed_byte: test",
    "shadow::merge_tests::changed_runs_are_exactly_the_bytes_that_differ: test",
    "shadow::merge_tests::changed_runs_are_the_ones_a_walk_byte_by_byte_finds: test",
    "shadow::perf4_tests::avx2_matches_scalar_unaligned_and_partial: test",
    "shadow::perf4_tests::idle_pool_hard_cap: test",
    "shadow::perf4_tests::sparse_merge_matches_dense_for_conflicts_and_tails: test",
    "shadow::piece_tests::pieces_cover_the_copy_as_the_compare_cuts_it: test",
    "shadow::relay_tests::a_range_stays_closed_until_every_flight_that_declared_it_is_done: test",
    "shadow::relay_tests::ranges_are_cut_out: test",
    "shadow::relay_tests::the_merge_stores_only_what_the_card_changed: test",
    "shadow::relay_tests::title_bytes_not_yet_on_the_card_are_not_taken_for_shader_writes: test",
    "shadow::relay_tests::two_flights_overlapping_ranges_and_a_cpu_write_in_between: test",
    "shadow::stale_tests::pages_never_taken_are_stale_written_or_not: test",
    "shadow::wide_tests::all_jobs_run_before_wide_returns: test",
    "shadow::wide_tests::copies_cut_into_jobs_copy_the_same_bytes: test",
    "shadow::wide_tests::pieces_found_wide_are_those_found_one_by_one: test",
    "shadow::window_tests::an_ask_takes_the_longest_window_that_holds_it: test",
    "shadow::window_tests::overlapping_windows_cover_their_memory_once: test",
    "shadow::window_tests::tails_run_to_the_cells_end_and_the_longest_is_taken: test",
    "shadow::window_tests::the_grid_is_a_power_of_two_or_the_default: test",
    "shadow::window_tests::windows_hold_their_ask_on_the_grid: test",
    "shot::tests::the_formats_shown_are_the_ones_the_pictures_decode: test",
    "spread::tests::a_pinning_of_the_title_is_within_the_console_s_sixteen: test",
    "spread::tests::only_crowded_groups_are_widened: test",
    "spread::tests::this_process_has_threads_and_they_have_masks: test",
    "texback::checked_preview::ai2_preview_native::actual_preview_refusal: test",
    "texback::checked_preview::ai2_preview_native::actual_preview_replay: test",
    "texback::tests::only_readbacks_for_changed_allocations_are_invalidated: test",
    "texture::title_memory_tests::an_uncommitted_tail_reads_as_zeros: test",
    "texture::title_memory_tests::the_small_texture_of_runs_72_and_73_detiles_the_same_both_ways: test",
    "tiles::tests::card_wrote_failure_does_not_poison_card_mask: test",
    "tiles::tests::floor_saturates_instead_of_wrapping: test",
    "tiles::tests::levels_on_demand_on_the_card: test",
    "tiles::tests::show_from_clamps_2d_and_2d_array_and_adjusts_min_lod: test",
    "watch::mapping_tests::mapping_epoch_changes_at_writer_boundaries: test",
    "watch::mapping_tests::reads_in_place_and_remappings_wait_for_each_other: test",
    "watch::tests::a_page_of_many_views_is_guarded_one_view_at_a_time: test",
    "watch::tests::a_range_that_begins_in_an_unmapped_block_is_guarded: test",
    "watch::tests::a_view_mapped_beside_a_guarded_one_makes_it_check_again: test",
    "watch::tests::a_write_is_reported_at_every_checked_view: test",
    "watch::tests::a_write_through_another_view_is_reported_at_the_guarded_one: test",
    "watch::tests::a_write_told_at_one_view_is_reported_at_the_others: test",
    "watch::tests::kernel_reads_into_guarded_blocks_after_opening: test",
    "watch::tests::ranges_past_the_address_space_end_do_not_overflow: test",
    "watch::tests::unmapped_blocks_are_reported_once_until_mapped: test",
    "watch::tests::writes_in_partly_committed_view_blocks_are_reported: test",
    "watch::tests::written_pages_are_reported_to_every_asker: test"
])
EXPECTED_IGNORED = frozenset([
    "drvwatch::tests::an_entry_written_reaches_a_subscription: test",
    "host::batch::texture_checks_per_submission: test",
    "indirect::bare_cost::bare_command_cost: test",
    "indirect::bench::bench_indirect_draw_barriers: test",
    "profile::tests::what_looking_costs: test",
    "texback::checked_preview::ai2_preview_native::actual_preview_refusal: test",
    "texback::checked_preview::ai2_preview_native::actual_preview_replay: test",
    "tiles::tests::levels_on_demand_on_the_card: test"
])

def parse_receipts(stdout, stderr, case):
    markers = ("checked_adapter", "preview_footprint", "preview_delivery",
               "preview_execution", "preview_replay", "preview_refusal")
    # verify_case has already required exactly one canonical libtest name line.
    # The actual test names contain receipt marker substrings.
    name_line = f"test {NAMES[case]} ... ok"
    if any(line != name_line and any(k in line for k in markers)
           for line in stdout.splitlines()):
        raise ValueError("receipt in stdout")
    rows = [line for line in stderr.splitlines() if any(k in line for k in markers)]
    if len(rows) != (9 if case == 0 else 2):
        raise ValueError("missing, duplicate or displaced preview receipts")
    signed = r"(0|-?[1-9][0-9]*)"
    unsigned = r"(0|[1-9][0-9]*)"
    m = re.fullmatch("checked_adapter actual_high=" + signed + " actual_low=" + unsigned
                     + " warp_high=" + signed + " warp_low=" + unsigned + " software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")
    if case == 1:
        if rows[1] != "preview_refusal selected=1 recorded=0 stale=1 submitted=0 missing=1 classifier=12 cleanup=1":
            raise ValueError("refusal receipt mismatch")
        return
    m = re.fullmatch("preview_footprint lower=" + unsigned + " total=" + unsigned
                     + " extent=" + unsigned, rows[1])
    if not m:
        raise ValueError("malformed footprint")
    lower, total, extent = map(int, m.groups())
    if not 2563 <= lower <= total <= extent <= 65536 or extent < 2816 or extent % 256 or lower % 256 != 3:
        raise ValueError("footprint bounds")
    widths = None
    for execution in (1, 2):
        index = 2 + 3 * (execution - 1)
        for ordinal in (0, 1):
            expected = (
                f"preview_delivery execution={execution} ordinal={ordinal} required=2560 "
                "preserve_attempted=1 preserve_requested=2560 preserve_success=1 preserve_done=2560 "
                "transfer_attempted=1 transfer_requested=2560 transfer_success=1 transfer_done=2560 "
                "mapped=1 unmapped=1 tiles=4 outcome=Complete semantic=Unresolved gpu_active=48 padding=2512 guards=62976"
            )
            if rows[index + ordinal] != expected:
                raise ValueError("delivery receipt mismatch")
        m = re.fullmatch(
            f"preview_execution execution={execution} submitted=1 fence=1 healthy=1 selected=2 recorded=2 delivered=2 missing=1 extent={extent} width0="
            + unsigned + " width1=" + unsigned, rows[index + 2])
        if not m:
            raise ValueError("execution receipt mismatch")
        observed = tuple(map(int, m.groups()))
        if any(not extent <= width < 2**64 for width in observed) or (widths is not None and observed != widths):
            raise ValueError("readback width changed or too small")
        widths = observed
    if rows[8] != "preview_replay executions=2 deliveries=4 distinct=1 geometry_mutated=1 geometry_refused=1 geometry_sentinel=1 cleanup=1":
        raise ValueError("replay final oracle mismatch")

def lf(data):
    return data.replace(b"\r\n", b"\n")

def clean_env():
    return {k:v for k,v in os.environ.items()
            if not k.upper().startswith(("VICTORY_", "RUST_TEST_", "AI2_", "AI5_", "AI6_"))
            and k.upper() not in ("CARGO_TARGET_DIR", "CARGO_BUILD_TARGET_DIR")}

def inventory(root):
    result = {}
    def walk(directory):
        for p in sorted(directory.iterdir()):
            rel = p.relative_to(root).as_posix()
            if rel == ".git":
                continue
            if p.is_symlink() or p.is_junction():
                raise ValueError("unexpected link in disposable checkout: " + rel)
            if p.is_dir():
                result[rel] = ("dir",)
                walk(p)
            elif p.is_file():
                with p.open("rb") as f:
                    result[rel] = ("file", hashlib.file_digest(f, "sha256").hexdigest())
            else:
                raise ValueError("unexpected path type: " + rel)
    walk(root)
    return result

def direct(args, target, env):
    try:
        p = subprocess.run(args, cwd=target, env=env, capture_output=True,
                           text=True, errors="replace", timeout=60)
    except subprocess.TimeoutExpired as exc:
        for label, stream in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            print(label + " (partial):", flush=True)
            if stream:
                print(stream.decode("utf-8", errors="replace") if isinstance(stream, bytes) else stream, flush=True)
        raise
    print("stdout:\n" + p.stdout, flush=True)
    print("stderr:\n" + p.stderr, flush=True)
    return p

def verify_case(stdout, stderr, code, case, total):
    if case not in range(len(CASES)) or total != 221:
        raise ValueError("unsupported case or discovery")
    out = stdout.splitlines()
    err = stderr.splitlines()
    if any(re.search(r"\bpanicked at\b|\bthread .* panicked\b", l, re.IGNORECASE) for l in out + err):
        raise ValueError("unexpected panic")
    def framing(line):
        return ("test result:" in line
                or re.search(r"\btest\s+\S+\s+\.\.\.", line)
                or re.match(r"^\s*test\s", line)
                or re.search(r"\brunning\s+\d+\s+tests?\b", line))
    if any(framing(l) for l in err):
        raise ValueError("unexpected libtest framing in stderr")
    frames = [l for l in out if framing(l)]
    name_line = f"test {NAMES[case]} ... ok"
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; " + str(total - 1) + r" filtered out; finished in [0-9]+(?:\.[0-9]+)?s"
    if (code != 0 or len(frames) != 3
            or frames[:2] != ["running 1 test", name_line]
            or not re.fullmatch(summary, frames[2])):
        raise ValueError("missing exact normal receipt")
    parse_receipts(stdout, stderr, case)

def self_check_receipt_parser():
    """Synthetic parser controls only; not native execution evidence."""
    adapter = "checked_adapter actual_high=0 actual_low=23932 warp_high=0 warp_low=23932 software=1"
    replay = [adapter, "preview_footprint lower=2563 total=2563 extent=2816"]
    for execution in (1, 2):
        for ordinal in (0, 1):
            replay.append(
                f"preview_delivery execution={execution} ordinal={ordinal} required=2560 "
                "preserve_attempted=1 preserve_requested=2560 preserve_success=1 preserve_done=2560 "
                "transfer_attempted=1 transfer_requested=2560 transfer_success=1 transfer_done=2560 "
                "mapped=1 unmapped=1 tiles=4 outcome=Complete semantic=Unresolved gpu_active=48 padding=2512 guards=62976")
        replay.append(
            f"preview_execution execution={execution} submitted=1 fence=1 healthy=1 selected=2 recorded=2 delivered=2 missing=1 extent=2816 width0=2816 width1=2816")
    replay.append("preview_replay executions=2 deliveries=4 distinct=1 geometry_mutated=1 geometry_refused=1 geometry_sentinel=1 cleanup=1")
    refusal = [adapter, "preview_refusal selected=1 recorded=0 stale=1 submitted=0 missing=1 classifier=12 cleanup=1"]
    for case, rows in enumerate((replay, refusal)):
        name = f"test {NAMES[case]} ... ok"
        out = f"\nrunning 1 test\n{name}\n\ntest result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 220 filtered out; finished in 0.09s\n"
        err = "\n".join(rows) + "\n"
        verify_case(out, err, 0, case, 221)
        bad = (
            (out + rows[-1] + "\n", err, 0),
            (out.replace(name, name + " " + rows[-1]), err, 0),
            (out + name + "\n", err, 0),
            (out, err + rows[-1] + "\n", 0),
            (out, err.replace(rows[-1], "prefix " + rows[-1]), 0),
            (out + rows[-1] + "\n", "\n".join(rows[:-1]), 0),
            (out, err, 1),
        )
        for bad_out, bad_err, code in bad:
            try:
                verify_case(bad_out, bad_err, code, case, 221)
            except ValueError:
                continue
            raise ValueError("synthetic receipt parser accepted malformed input")
    print("synthetic receipt parser controls: 2 valid, 14 invalid rejected; not native receipts", flush=True)

def run_exact(exe, target, release, case):
    profile = "release" if release else "debug"
    env = clean_env()
    flags = {"VICTORY_D3D12_WARP": "1", "VICTORY_SWEEP": "0", "VICTORY_TEXTURE_BACK": "7x3f61"}
    env.update(flags)
    print(f"profile={profile} case={CASES[case]} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(flags, sort_keys=True) + " VICTORY_COPY_MODE=absent VICTORY_COPY_ASK=absent", flush=True)
    def discover(ignored):
        args = [str(exe), "--list"] + (["--ignored"] if ignored else [])
        p = direct(args, target, env)
        if p.returncode or any(re.search(
                r"\b\S+: (?:test|benchmark)\b|\b\d+ tests?, \d+ benchmarks?\b|\bpanicked at\b",
                line, re.IGNORECASE) for line in p.stderr.splitlines()):
            raise ValueError("discovery exit or contradictory stderr")
        lines = [l for l in p.stdout.splitlines() if l]
        if not lines:
            raise ValueError("empty discovery")
        m = re.fullmatch(r"(0|[1-9][0-9]*) tests?, (0|[1-9][0-9]*) benchmarks?", lines[-1])
        if not m or int(m[2]) != 0:
            raise ValueError("unexpected discovery summary")
        tests = lines[:-1]
        if len(tests) != int(m[1]) or len(set(tests)) != len(tests) or any(not re.fullmatch(r"\S+: test", l) for l in tests):
            raise ValueError("inconsistent discovery inventory")
        if any(tests.count(n + ": test") != 1 for n in NAMES):
            raise ValueError("missing exact case")
        return set(tests)
    full = discover(False)
    ignored = discover(True)
    if full != EXPECTED_FULL or ignored != EXPECTED_IGNORED or len(full) != 221 or len(ignored) != 8:
        raise ValueError("discovery differs from reviewed #148 replacement inventory")
    print(f"discovered_total={len(full)} ignored_total={len(ignored)}", flush=True)
    p = direct([str(exe), NAMES[case], "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"], target, env)
    print(f"child_exit case={CASES[case]} code={p.returncode}", flush=True)
    verify_case(p.stdout, p.stderr, p.returncode, case, len(full))
    print(f"accepted case={CASES[case]} exit={p.returncode} kind=normal", flush=True)
    return full, ignored

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    self_check_receipt_parser()
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-checked-preview-") as tmp:
        owned = Path(tmp).absolute()
        if owned.is_symlink() or owned.is_junction() or not owned.is_dir():
            raise ValueError("unexpected temporary root type")
        canonical = owned.resolve(strict=True)
        if not owned.samefile(canonical) or canonical == ROOT or ROOT in canonical.parents or canonical in ROOT.parents:
            raise ValueError("temporary root identity or overlap")
        target = canonical / "runtime"
        if target.exists() or target.is_symlink() or target.is_junction():
            raise ValueError("runtime child must be absent")
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900, env=clean_env())
        if (target.is_symlink() or target.is_junction() or not target.is_dir()
                or target.resolve(strict=True) != target or not owned.samefile(canonical)
                or not target.parent.samefile(canonical)):
            raise ValueError("runtime child identity")
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        before = inventory(target)
        cmd = [sys.executable, str(ROOT / PREPARER), str(target)]
        subprocess.run(cmd, check=True, timeout=120, env=clean_env())
        if inventory(target) != before:
            raise ValueError("dry run changed checkout")
        subprocess.run(cmd + ["--apply"], check=True, timeout=120, env=clean_env())
        after = inventory(target)
        if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != set(POST):
            raise ValueError("unexpected full checkout delta")
        for path, expected in POST.items():
            if blob(lf((target/path).read_bytes())) != expected:
                raise ValueError("actual postimage identity: " + path)
        print(f"inventory_entries={len(before)} changed=3 upstream={UPSTREAM}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        digests = set()
        baseline = None
        for release in (False, True):
            exe = build(target, release)
            digest = hashlib.sha256(exe.read_bytes()).hexdigest()
            if digest in digests:
                raise ValueError("debug and release executable identities must differ")
            digests.add(digest)
            for case in range(len(CASES)):
                if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
                    raise ValueError("profile executable changed before case")
                observed = run_exact(exe, target, release, case)
                if baseline is None:
                    baseline = observed
                elif observed != baseline:
                    raise ValueError("discovery changed across cases")
                if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
                    raise ValueError("profile executable changed after case")
    print("Four exact checked texture preview native cases passed; no semantic delivery, production or gameplay proof.")

if __name__ == "__main__":
    main()
