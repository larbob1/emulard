# HLE native suite registration proposal

Review-only, coordinator-owned registration. The exact historical PR #51 baseline native proof remains unchanged.

The four test modules previously required independently pristine xasync.rs sources. This preview explicitly composes their two overlapping spawn hooks, the separate delayed delivery hook, and four unchanged pinned test modules. The original source and each fixture must match their exact Git blob; any changed source, missing anchor, duplicated module, or altered fixture fails closed. Output is exclusive-create only and does not modify its input. Outside cfg(test), the spawn closure still calls self.work() and delayed delivery remains unchanged.

## Proposed isolated validation

Prepare the exact pinned upstream via the existing coordinator-owned process. Verify pristine xasync.rs blob 068d75f2a8a50b7a4f0ec7a45e9c849c657bcde1. Generate the preview with tools/preview_hle_native_suite.py using a new temporary output file, then copy only that verified postimage into the disposable prepared checkout. No owner-machine or game files.

Run each of the following filters in its own fresh process using cargo test --locked -p victory-hle --lib FILTER -- --ignored --test-threads=1. Require exactly one passing test, zero failed, zero ignored in each invocation, with external watchdog and unwind-capable test profile for the panic fixture.

- hle_pool_native_review::reentrant_pool_callback_progress
- hle_pool_gated_native_review::pending_start_and_idle_notification
- hle_pool_spawn_failure_review::spawn_panic_preserves_queued_work
- hle_delayed_native_review::delayed_queue_lifetime_and_termination

Do not run the four ignored tests together in one process: their test-only statics and global persistent pool are intentionally fresh-process scoped. Run existing xasync::tests:: (seven cases) and exact dependent callback baseline separately; verify release and diagnostics builds. No global env toggles or scheduling changes. The composed hook path has not yet been compiled or executed. The failure case is an injected Rust panic, not real OS failure, and delayed delivery characterizes existing behavior without claiming API conformance.

This consolidation should reduce duplicate source-preparation and compilation effort; no time savings measured. No optimization policy, launch or merge approval. D22/D23/D24 remain unchanged.
