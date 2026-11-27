# P03 — minimal CPU-only trace: coordinator review proposal

Pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. This is a
design and a portable state prototype, NOT a prepared runtime patch. No
producer has been registered; no shared builder/CI change or new runtime
flag has been made. Coordinator and AI 2 approval required before wiring.
AI 1 owns memory spans, AI 2 owns GPU submission/completion/fence spans.

## Exact initial upstream anchors (read-only inspection)

| Source / symbol | Proposed CPU-only observation | Explicit non-claim |
| --- | --- | --- |
| crates/victory-gpu/src/queue.rs::execute (around 1033–1043) | outer call immediately before execute_now and after it returns, on caller thread | not CPU busy time or GPU execution; nested work included |
| queue.rs::present (around 1288–1305) | entry before present_now; end immediately after present_now returns, before add(PresentUs), framelog::frame and diagnostic fence pacing | title present-call return, not display completion |
| crates/victory-gpu/src/frame.rs::wait (around 120–157) | timestamp around actual thread::sleep branch, not the requested wait.min(limit) value | not total CPU time and not a GPU fence |
| crates/victory-gpu/src/framelog.rs::frame (around 542–600) | existing report unaffected; optional separate handoff of bounded numeric record | current now is after cardmeter::collect; cannot treat it as exact present-call boundary |

Existing queue::present_now may call send_behind, release_held_now and
settle_for_present. With present_behind/late modes, host work may happen
after the title call returns. Never call that boundary displayed frame or
GPU completion. Diagnostic fence pacing after framelog::frame also falls
outside that outer present span. No changes to scheduling, fences, waits,
existing counters or draw semantics. Do not add record-list instrumentation
until the outer spans are measured; nested inclusive timers overlap.

## Schema mapping

Separate schema cpu_trace_v1, not the synchronized causal DAG in
performance-critical-path.md. All timestamps integer nanoseconds from a
single host Instant origin, all selected spans on the same presenting
thread generation. Frame sequence counts consecutive title present-call
return windows; first return arms capture and emits no window. One record:

    {"schema":"cpu_trace_v1","boundary":"present_call_return","sequence":1,"start_ns":100,"end_ns":200,"dropped":0,"invalid":0,"thread_changed":false,"present_ok":true,"cpu_window_complete":true,"spans":[{"kind":"execute","start_ns":110,"end_ns":120},{"kind":"pace_sleep","start_ns":130,"end_ns":140},{"kind":"present_call","start_ns":150,"end_ns":200}]}

Allowed kinds execute, pace_sleep, present_call. No raw OS thread IDs,
pointers, process/title strings or GPU identifiers. cpu_window_complete
means the selected outer CPU call observations are structurally complete,
not that all CPU work or all dependencies were observed. A failed HRESULT
marks the window incomplete, but S_OK is not visual correctness. Endpoints
must be strictly positive duration, nonoverlapping and within the window.
Thread change, loss, cap, reversal, missing final present, crossed boundary
or nested selected spans mark incomplete. No inferred serial dependency
from timestamps alone. The full dependency analyzer must not accept this
schema as calibrated GPU evidence. Later explicit edges and actual
completion correlation are a separate schema/owner agreement, not a
rename or extrapolation.

## Proposed wiring (not authorized yet)

- Default off VICTORY_CPU_TRACE=1, cached OnceLock check before timestamps,
  thread-local allocation or event construction. Explicit diagnostic build
  initially. Disabled path must not allocate or call Instant::now for new
  trace. No new runtime flags until approved.
- Portable prototype Buffer is a serial model, not a thread-safe integration.
  Actual wiring: retain per-thread bounded state (256 spans maximum), a
  monotonic presentation sequence and thread generation token, no raw IDs
  emitted. A present-thread change invalidates the affected window; stale
  TLS from a former presenting thread must reset on epoch change before it
  can publish. Multiple concurrent presents cannot be silently serialized
  into fake timestamps: reject ambiguous ordering and account lost windows.
  Reuse capacity in actual implementation; prototype transfers Vec ownership.
- Timestamp the exact outer call boundary using one host Instant epoch.
  Derive each duration from start/end, not from existing cumulative counters.
  If elapsed conversion overflows or timestamps collide, invalidate the
  record. Do not move or extend memory/GPU lock critical sections.
- Use a bounded output queue, never blocking the normal runtime path.
  Emit completed records outside mapping/queue locks; count dropped output
  windows and expose sequence discontinuities. No synchronous per-span
  tracing. If output publication cannot be made bounded, stop capture
  rather than slow the runtime indefinitely. Capture limited to one
  explicitly requested steady-state window (initial cap 600 frames).
- Preserve complete separation from P03 full GPU dependency schema. AI 2
  must review queue wrapper and async presentation semantics; AI 1 must
  review any later mapping spans. Do not add GPU clock calibration here.

## Acceptance of instrumentation

1. Review these exact anchors against prepared cumulative source; check
   overlapping patch hunks and get coordinator + AI 2 agreement.
2. Integrate only the approved wrappers and framelog handoff in a separate
   branch, with deterministic tests for disabled path, capacity, loss,
   thread switches, concurrent presentation, malformed/reversed boundaries,
   failed calls and full capture stop. Existing portable model exercises
   serial state, not TLS concurrency or real runtime I/O.
3. Compile both runtime profiles and run existing native suites. Verify
   emitted format on synthetic native run and then owner Proton smoke.
4. Measure instrumentation on/off overhead with identical scene/flags;
   record CPU utilization and frame tails. No FPS gain or critical path
   claim merely from collecting CPU call intervals.

No native runtime edits or gameplay evidence in this proposal. Request
coordinator review before any shared build registration. Existing P18
host sampler can collect resource pressure independently.
