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

## Offline CPU-only summary (implemented)

    python3 tools/cpu_trace_report.py local-cpu-trace.jsonl > cpu-summary.json

Consumes the separate numeric JSONL records defined above, not ordinary frame
logs or the causal GPU trace. The portable producer has no runtime wiring yet.
Checks the 256-span and 600-window limits, exact boundary and schema, consecutive
sequence starting at 1, adjacent timestamps, complete producer flags, valid
nonoverlapping selected spans and exactly one terminal present call. Any
rejection or sequence gap suppresses the aggregate; no missing trailing record
detection is possible without a future capture-end record. Output is numeric
elapsed-weighted category fractions and per-window median/p95/p99/max (including
zero for absent categories), call counts and unattributed elapsed fraction.
Outer calls include waiting and nested work; neither CPU busy time nor display
FPS is inferred. No raw timestamps or identifiers exported. Exit 0 means
supplied records structurally usable, 1 unavailable, 2 incomplete/invalid.

## Bounded concurrent capture prototype (approved isolated model)

The portable probe now also implements a process-wide controller, scalar TLS
session/thread/epoch identity, non-transferable tickets, at most eight queued
windows (256 spans each), and one active window, capped at 600 attempted
windows. No per-thread span vectors or thread registry are retained. A disabled
or stopped begin returns before touching TLS or acquiring the capture mutex.
The proposed runtime must also check enabled before obtaining timestamps.
Producer acquisition is try-lock only; contention stops observation rather than
stalling gameplay. Concurrent presents, stale tickets and queue overflow stop
capture; thread changes and invalid windows are counted. A full queue is never
overwritten. The consumer takes ownership of one record before serialization.
No I/O occurs inside the state model. A fault status can represent unknown
additional loss, not an exact count of every omitted event.

Terminal status is a model-only receipt: stop reason, attempted, drained,
invalid and dropped windows. A clean cap and fully drained queue are necessary
for complete observation; actual consumer write/flush acknowledgement and
capture-end record are not implemented. The offline v1 summary still only
validates supplied JSONL; it cannot certify the terminal receipt. Do not treat
partial records from a faulted session as a complete capture. In real wiring
limit consumer ownership to one record, stop/acknowledge in-flight tickets
before terminal publication, and validate end-of-capture status. The model's
try-lock deliberately sacrifices a capture under contention (including the
consumer); overhead and a better producer design need real testing.

AI2 approved the narrow wrapper ownership scope in principle; coordinator
approval of exact prepared hunks and shared builder registration is outstanding.
The prototype has no runtime timestamp calls, no production flags, no writer,
and no actual runtime source changes. Compiled tests cover real-thread overlap
and contention plus stale epochs, disabled path, caps, thread changes and
bounded drain. CPU observation is not displayed-frame or GPU completion timing.

## Terminal handshake and writer prototype

A producer admission gate closes on stop and waits for already admitted
operations to retire before terminal receipt construction. Outstanding
non-present tickets at a window boundary stop capture rather than certify an
incomplete window. One writer lease at a time is allowed; write_next performs
write and flush outside the capture lock and acknowledges the sequence only
on success. A failed write or flush leaves the capture unpublishable.
No runtime writer thread or filesystem publication has been installed.
A terminal receipt uses schema cpu_trace_end_v1 with numeric code (1 = cap),
expected, attempted, drained, written, invalid_windows, dropped_windows and
boolean complete. Clean receipt requires all counts equal to capture cap,
zero invalid/dropped and no outstanding tickets. For production, use a single
writer, emit and flush the footer only after quiescence, and publish a new
local file only after success (temporary file + successful close/rename;
flush alone is not disk durability). No footer on write failure.

    python3 tools/cpu_trace_report.py local-cpu-trace.jsonl --require-terminal

Strict mode requires the matching receipt as final record. Legacy mode remains
for synthetic fixtures/structural analysis, explicitly terminal_verified false
without a receipt. This is count/structure validation, not proof of capture
provenance, clock accuracy, storage durability or visual FPS. The prototype
still has no runtime hooks or approved shared registration.

## Exact review-only hook preview and file writer

The unregistered tool tools/propose_cpu_trace_hooks.py accepts a separately
prepared runtime root and prints a unified diff, never modifies its files.
Five exact anchors were checked against pinned upstream 51700c6d; the
prepared cumulative patch stack still requires coordinator verification.
Review the diff and proposed cpu_trace.rs module (portable model + bridge):

    python3 tools/propose_cpu_trace_hooks.py ../runtime-combined > cpu-hooks-review.diff

No builder registration or prepared source edits in this PR. Proposed module
registration in lib.rs beside framelog is diagnostics + Windows only. The
four wrapper replacements are execute/present and both actual sleep branches;
existing framelog::frame and pacing/return/error behavior unchanged. Existing
framelog wall timer will include new hook overhead when enabled. The bridge
reserves a ticket before timestamping, samples end before existing counters,
and reports HRESULT success via nonnegative result. Disabled path caches
configuration once and returns before new clocks, capture locks, TLS or
allocation (environment query once; initial enabled setup may allocate and
spawn on caller). This is not a proof of zero overhead or absence of all
caller-held locks; coordinator must review callers and measure off/on.

Proposed opt-in VICTORY_CPU_TRACE=1 AND VICTORY_CPU_TRACE_PATH=<fresh local file>.
One process-wide worker creates a new .partial file, writes/flushes records
outside the capture mutex, stops after 600 windows or a 900s polling deadline,
and publishes only a complete footer + successful file sync using a same-
directory hard link (no overwrite, unsupported FS refuses). The deadline is
checked between writes, not an OS I/O timeout. No join on gameplay path;
process exit can leave a partial file. Never use .partial as accepted evidence
(including a complete-looking footer if final publication failed). File sync
is not directory durability. Capture begins on first enabled hook; warmup
selection, late activation, and instrumentation on/off overhead are pending.
The fail-closed try-lock may abort under writer contention; no speed claim.
No actual full runtime compile or Proton validation yet. Exact hunks and
builder registration require D09 coordinator approval; AI2 narrow wrapper
scope consent is recorded in #13.
