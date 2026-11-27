# Idle retirement native suite (review-only)

After exact composed baseline validation (26a1a45b), register this separate test-only suite in a disposable prepared checkout. It appends three independently generated modules to the pristine pinned xasync.rs blob 068d75f2a8a50b7a4f0ec7a45e9c849c657bcde1; existing production bytes are unchanged. Exact fixture blob pins, unique module markers and exclusive output creation are enforced. Do not apply the baseline and retirement composers sequentially to one file: each requires pristine source.

Generate an exclusive preview file with python tools/test_hle_idle_suite_preview.py SOURCE OUTPUT, then copy only the reviewed postimage into the isolated native checkout. Run each filter separately in a fresh process with an external bounded watchdog, cargo test --locked -p victory-hle --lib FILTER -- --ignored --test-threads=1. Require exact 1 passed, 0 failed, 0 ignored:

- hle_idle_native_review::idle_native_baseline
- hle_idle_native_review::idle_native_candidate
- hle_idle_boundary_review::empty_wake_then_submission_reuses_idle_worker
- hle_idle_boundary_review::expiry_holds_lock_then_submission_starts_replacement
- hle_idle_cleanup_native_review::retired_worker_cleanup_does_not_supply_capacity

Require existing xasync tests, dependent callback test and both builds. Gate release success is now observed by the receiving worker, not inferred from sender success. The cleanup test checks the first handle is still unsignaled immediately before release, waits for actual thread termination and checks TLS destructor count. The blocking gate is before thread-body return, not in a TLS destructor.

This is not proof of actual title-image DLL/TLS notification compatibility, native runtime retirement integration, performance, or a production timeout. The clone preserves baseline admission and has illustrative test durations only. No title launch, owner-machine access, shared CI registration or merge authority. D22-D25 unchanged.
