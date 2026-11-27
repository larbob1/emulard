# P03 — synchronized dependency trace contract (proposal)

The existing framelog is cumulative and many durations overlap. This offline
consumer is implemented and tested with synthetic records only. There is no
runtime producer yet; coordinator and graphics/memory owners must agree before
any instrumentation is inserted. Do not convert aggregate framelog columns into
dependency spans or claim an exclusive critical path from them.

## Numeric schema v1

One JSON object per line, one frame window from previous present completion to
current present completion. All timestamps are integer microseconds relative to
one monotonic host clock; GPU spans require measured clock calibration. Use only
local numeric frame/span IDs, no addresses, title strings or raw GPU identifiers.
Example (synthetic, not gameplay):

    {"schema":1,"frame":1,"clock":"host_monotonic_calibrated","start_us":0,"end_us":100,"complete":true,"lost_spans":0,"terminal":3,"spans":[{"id":1,"start_us":0,"end_us":40,"kind":"mapping","depends_on":[]},{"id":2,"start_us":40,"end_us":80,"kind":"gpu","depends_on":[1]},{"id":3,"start_us":80,"end_us":100,"kind":"present","depends_on":[2]}]}

Allowed kinds: cpu_record, cpu_submit, mapping, texture, pipeline, gpu,
fence_wait, storage, present, other. Every span has a unique frame-local ID and
positive duration. Dependencies denote observed completion-before-start
requirements, not merely temporal ordering. The terminal is a present span
ending exactly at the frame window end. For this first version spans must lie
wholly within one frame. Cross-frame work, unresolved carry-in, inclusive waits
overlapping their dependencies, clock uncertainty and dropped records must
cause incomplete evidence rather than fake edges or silently clipped work.
Split inclusive wait into nonoverlapping attributable pieces only when causal
timestamps actually support that split. Explicitly record all dropped spans
and mark complete false on truncation, unresolved correlation, or calibration
failure. Completeness is an assertion by the producer; the analyzer cannot
detect every missing whole frame or dependency.

## Producer proposal for coordination

- Frame owner: read-only anchor framelog::frame and the actual present
  completion boundary. Agree with graphics owner on identifiers and when
  a completed dependency may be published; do not change draw/fence order.
- CPU owner: instrument entry/exit of the exact submit and record anchors
  agreed with graphics, with submit/queue dependency IDs rather than addresses.
- Memory owner: agree on remap lock acquisition/release and reader waits;
  distinguish acquisition wait from held duration; do not move locks or
  invalidate views for instrumentation.
- GPU owner: calibrate GPU timestamps against a monotonic host clock and
  correlate submitted work/fences; delayed cardmeter aggregate data is
  insufficient. Preserve all existing completion rules.
- Storage owner: only attach a completion dependency when the frame actually
  waits for that request; background worker activity is not a critical path.

Use an opt-in bounded capture, default off, thread-local buffers where possible,
drop accounting and no extra synchronization on the normal path. Compare
instrumentation on/off overhead and verify both builds and native/Proton
correctness. Exact prepared symbols, registration and test plans require
coordinator agreement. No shared file or runtime edits in this candidate.

## Analyze locally

    python3 tools/critical_path_report.py local-trace.jsonl > numeric-chain.json

Exit 0 means supplied records passed structural checks, 1 means unavailable,
2 means at least one rejected record or no usable frames. Do not upload raw
traces. Numeric output omits original IDs, paths and arbitrary labels. Output
keeps each frame's metrics but suppresses the aggregate median if any records
are rejected; no performance gate is inferred.

The analyzer finds the ancestors of the presentation terminal and the longest
sum of nonoverlapping durations along explicit edges. A longer parallel branch
may determine that lower bound, but gaps and missing causal relationships can
change actual latency attribution. This is not a complete scheduling model or
an optimization prediction. Union length counts each covered microsecond once;
the aggregate minus union measures excess overlap, not wasted work. Unrelated
spans are not counted on the presentation dependency chain. Equal-length
chains suppress category attribution to avoid arbitrarily picking a bottleneck.
Never interpret unaccounted wall time as idle time or GPU union as utilization.
Owner gameplay tests and independent correctness evidence remain necessary.
