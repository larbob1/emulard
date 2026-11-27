# P22: cache directory ownership review

Scope: graphics #14, pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4.
Test only. No change to the driver, cache format, file mapping, runtime
defaults or actual cache directory.

## Source evidence

* `pipeline/library.rs::save` derives the staging filename from
  LIBRARY_FILE.with_extension("tmp"); the process-local save gate cannot
  coordinate independent processes.
* `write_atomically` similarly derives one fixed temporary early-list
  filename. The existing USED set is a process-local snapshot.
* `replace_library` publishes a pending file when NEXT already exists;
  its existence check and rename are not a cross-process transaction.
* Startup `Blob::of` may promote NEXT; `open` may rename a rejected
  library. A writer-only lock around save would not protect those operations.
* Distinct temporary names prevent accidental staging aliasing but cannot
  merge independently built opaque driver blobs.

The new test harness extracts the current actual Rust rename helper from
apply_pipeline_perf.py and invokes independent child processes on isolated
synthetic directories. It deliberately reproduces three counterexamples:
shared staging names, independent names with stale source snapshots, and
last-writer-wins publication to NEXT. Test success demonstrates the file
operation hazard, not that it occurred in any title run. It does not
instantiate D3D12, test a mapped Windows blob or infer RSS or FPS.

## Proposed boundary for a later candidate

Prefer one nonblocking directory-owner lease for the entire cache session,
acquired before any startup promotion, rejection rename, or save, not
just during publication. A non-owner must never alter that directory;
private cache directories or an explicitly reviewed read-only/no-cache
fallback are possible. Avoid removing a live lease by pathname, process-ID
guessing, or unsafe stale-lock cleanup. A platform-specific implementation
must establish exclusion across processes, release on process exit and
crash, behavior on unsupported filesystems, and compatible lock ordering.
Preserve the mapped blob's lifetime and driver validation. No opaque blob
merge is assumed. Do not change default policy without review.

Native tests required before promotion: two independent processes, owner
and contender, startup NEXT promotion and rejection while contested,
normal exit and abrupt termination, owner reacquisition, failure paths,
mapped-file lifetime, early-list behavior and cache-disabled fallback.
Review lock semantics on native Windows and Proton separately. Test only
synthetic private cache data; never touch title or existing user cache.

B003 reported no usable library and zero saved bytes; these hazards do
not explain that failure. Actual initialization HRESULT, cache ownership
evidence, and matched cold/warm gameplay remain outstanding.

## Linux lease feasibility (not runtime registration)

The separate Linux-only test uses a persistent sidecar and nonblocking
flock on an open file handle. The contender returns without writing the
synthetic marker if the lease is busy; an independent directory can
progress. The same sidecar inode survives normal exit and abrupt death
of the fixture's own child process. A directory symlink resolves to the
same sidecar. All waits have finite test deadlines. This does not prove
Windows byte-range locks, Wine/Proton interop, hostile directory changes,
network filesystems, or protection against non-cooperating writers.
Never delete/recreate the sidecar to recover a supposedly stale lock.

A separate source finding: upstream library.rs::save returns immediately
if library() is None, before snapshotting/writing USED. In the observed
no-library startup, this prevents the normal save path from persisting
early-list changes even if shader translation succeeds. It does not prove
whether a previous list already existed, or how much prewarming would
help. A future candidate could decouple early-list-only persistence from
driver library availability, but must first establish cache ownership,
preserve RenderDoc policy, retain dirty state on failed writes, and avoid
new shared-cache writes without coordinator approval. No such production
change is included here.

## Early-list-only protocol model

probes/early_list_persistence.rs models an independent early-list save
when no usable driver library exists. The external owner/policy booleans
are assumptions, not a real lease or RenderDoc check. A nonblocking save
gate serializes publications, the state mutex captures a sorted key
snapshot and consumes its dirty bit, and publication occurs outside that
mutex. Failed publication restores the dirty bit without erasing any
later note. Unwinding restores dirty and poisons the model save gate,
which then refuses further publication. No opaque library operation is
present. Seven cases exercise denial, retry, interleaved notes on success
and failure, busy save, duplicate keys and uncertain publication.

This is a model, not a source patch or a filesystem test. Actual runtime
integration must preserve EARLY_MAX and startup reading, existing
periodic/forced save semantics and lock order, RenderDoc exclusion,
directory ownership across startup/rename/save, publication atomicity,
dirty retry, and independent driver-library bookkeeping. Existing cache
writes are not authorized by this model. An interleaved callback simulates
a later note deterministically; it is not throughput or concurrent OS
evidence. No new runtime flag or title launch.

## Native Windows sidecar feasibility (test-only)

tools/test_pipeline_cache_native_lease.py adds an independent subprocess
probe. Linux uses flock, while native Windows Python calls LockFileEx
with exclusive and fail-immediately flags for byte zero of a persistent
sidecar. Only a lock conflict is classified as busy; other failures
must not publish. The child holds its own open file until exit. Four
cases cover normal close, abrupt termination of the fixture's child,
independent cache directories, and open failure. The marker is synthetic;
the sidecar content and file identity are checked after release.

Run the same fixture in isolated native Windows CI with Python
and separately on Linux. Linux success cannot validate the Windows
branch. Neither validates Windows calls under Proton, cross-platform
lock interoperability, alias handling on Windows, filesystem variation,
or library save/startup ordering. No new production API is selected.
The workspace declares Rust 1.88; do not silently introduce a newer
standard-library locking requirement. Existing lease and cache policy,
including RenderDoc exclusion, remain unchanged.
