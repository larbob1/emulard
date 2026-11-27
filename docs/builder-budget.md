# Builder preparation and budget controls

This revision adds early pipeline preparation only when the existing structure-builder opt-in is requested. It queues work on the existing compiler workers and keeps the all-or-none dispatch gate unchanged. It reports whether a failed pipeline has untranslated stages without including shader contents or identifiers. Earlier preparation may reduce first-use stalls; it cannot make an unsupported instruction translate.

EMULARD_PIPELINE_WORKERS optionally caps the number of concurrent compiler workers, from one to the existing default. Lower concurrency may reduce transient allocation peaks but can increase compilation latency. The default is unchanged.

When an explicit texture-copy budget is configured, admission now honors both that budget and the driver's video-memory budget (when available). This avoids the prior explicit-cap bypass. The existing default behavior is unchanged. This is an admission check, not a strict allocation cap: concurrent allocations or resource sizes can still overshoot it. More aggressive limits can produce missing textures. No active resources are evicted.

The pinned patcher validates all three source blobs before writing. Four Python tests and two Rust regression tests are included. Hardware rendering, memory usage, and new shader coverage are unverified. The runtime workflow uses a per-commit concurrency group to prevent later development commits from cancelling earlier compile checks.

Remaining translation failures require actual instruction-level error diagnostics and synthetic reproduction; no fallback that silently substitutes incorrect values is added.
