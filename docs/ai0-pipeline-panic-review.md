# EXT-01 — pipeline panic terminal publication review

Review only; no runtime recovery policy is selected or applied. [Scope claim](https://github.com/larbob1/emulard/issues/55#issuecomment-7224575653).

## Exact source
- Raw upstream fxceless/victory-fork 51700c6d43a3507fa65e50fe4bb64074ce706cd4, pipeline/make.rs b21b7163e0c4ec7deedd1f963d4383e311e9475a. Pending::make calls OnceLock::get_or_init with HostPipeline::new then takes DONE's lock and notifies. A Rust unwind from that initializer can leave the cell unset and bypass notification, the worker WAITING decrement and later work. Queue state remains MAKING; ready's timed waits do not establish progress. now() and the no-worker synchronous start also call make.
- Raw Cargo.toml 4e21b692d66103d990003164b6f1e4f700bc4086 does not specify panic=abort in release/diag; effective compiler configuration must still be verified.
- Emulard worker tracing patch f41f87c52fc671f384837693564b1337a18ce5bb changes the initializer. AI2 #14 exact 8687a88e566e7fb75917428eedbfa2d8226daeb9 and #42 exact 3029948c650c28f6baa8c069687dc584c5fbad49 include completion stripes. These overlap the notifier; don't blindly replace it with DONE.
- External [megafork commit b5fc030](https://github.com/rorodev6/victory-nvidia-megafork/commit/b5fc03002ef4ce7a8804322994b742afe0661980) catches the initializer and publishes None. Its empty-shader synthetic test invokes make_with on a manually spawned thread, not the real queue, accounting, wait predicates or driver. It establishes no Emulard result.

## Proposed gates before a port

1. Review actual prepared source including worker tracing, stripes, queue claims, synchronous now/start, caching and publication. Publish a terminal outcome inside the chosen OnceLock initializer, then notify using the same lock/selector as wait. Preserve exactly-once accounting for queued jobs, not direct now calls. Do not introduce new timeout or retry policy.
2. Do not treat every unwind as recoverable: audit HostPipeline::new and translation/link/cache/driver state and locks, partial side effects, FFI boundaries, panic hook and payload drop. Rust catch_unwind cannot rescue abort or arbitrary device/foreign exceptions; AssertUnwindSafe is an assertion, not a proof. Require explicit failure classification and safe continuation; no concealed missing draws or false FPS success. Logging or failure reporting must not defeat terminal publication. Distinguish refusal, panic and success in approved diagnostics; no new shared schema here.
3. Title-free native fixture: inject a known Rust panic at a narrow approved seam in a nonempty pipeline job; exercise actual queue claim, WAITING decrement, two real waiters, duplicate/now contention, ordinary refusal and a subsequent independently successful job. Test global and explicit striped modes, including collision and notification before waiter entry. Confirm no worker/capacity leak, no indefinite pending state, exact completion counters and no unintended cache publication. Preserve original queue semantics; bounded harness subprocess watchdog, not a production timeout.
4. Verify release/diagnostics effective panic strategy and both builds. Verify successful pipeline parity and failure telemetry, actual native receipts and matched Proton correctness via approved AI4 testing when required. Never count unsupported/skipped execution as a pass.

## Standalone model

`rustc --edition=2021 --test probes/pipeline_panic_review.rs -o /tmp/ai0-pipeline-panic-review`
Run the resulting test binary under a bounded external watchdog in an isolated environment. The five proposed tests use only synthetic string panics, local OnceLock/Condvar and manually constructed jobs. They are not tests of actual Pending, queues, stripes, driver, or GPU behavior. The modeled terminal refusal is not an approval to drop a draw. No runtime, builder, CI, flags or policy changes. AI1 exact review, AI2 affected owner, AI3 acceptance, AI4 REQUIRED/NOT REQUIRED rationale and owner merge authority remain required.
