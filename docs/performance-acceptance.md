# P20 — local owner-attested gameplay acceptance

Use this tool only after native/Proton smoke tests. It does not run the emulator, count visible frames, validate a driver, or independently establish rendering correctness. Keep all source logs and the manifest local. Only share reviewed numeric JSON output. Compare Windows and Proton separately; use the same exact revision, platform, hardware, settings, scene and cache state for each set of repeats.

Capture the measured steady-state window (after warmup), with frame logging enabled. The manifest references logs containing the measured window only, not startup/warmup. If it is not possible to isolate this window with existing logging, do not attest that the window matches. Count correctly displayed frames by a suitable external observation/measurement; the present-to-present counter alone cannot establish this. The evaluator refuses missing or inconsistent evidence and does not infer visible frames.

Create a local JSON manifest with a top-level configuration object and runs array. Each run must copy the exact configuration object. Required configuration strings: revision (full 40-digit commit SHA), platform (include Proton version when applicable), driver, hardware, profile, scene (local label), settings, cache_state, flags, resolution, warmup. These fields are compared locally and never exported.

Each run has a distinct id, local log path (relative to manifest or absolute), elapsed_seconds (measured wall seconds), correctly_displayed_frames (nonnegative integer), configuration, and checks object. Set each check to true only when verified by the operator: full_scene, responsive_controls, no_crash, no_missing_required_draws, no_invalid_memory_access, measured_window_matches_log, independent_trial. Use false for observed failure and omit unknown checks. Never guess counts or label unverified checks true.

Run:

    python3 tools/gameplay_acceptance.py local-manifest.json > acceptance.json

Exit 0 means the supplied evidence meets owner-attested M5 criteria, not independent verification; 1 means malformed/unavailable input; 2 means M5 failed or evidence is insufficient. All milestones remain separately reported. All runs, not just the best three, must meet a gate. Each gate requires three independent trials, complete evidence, no reported dropped draws and verified operator checks. M5 additionally requires 600 seconds per run, >=30 correctly displayed frames/s, p95 <=50 ms and p99 <=100 ms. Lower gates have no fixed duration in the roadmap; document a repeatable scene length. The evaluator compares the rounded frame-duration sum with operator wall time (one-second boundary tolerance plus 0.5 ms per frame), requires valid interval and detailed samples and rejects visible counts exceeding the detailed frame count. The first present and final partial batch may not be represented; align the measured window or repeat the trial rather than inventing samples.

Distinct paths, IDs and SHA-256 content checks reject exact accidental duplicates, but cannot prove independent runs. Missing entire records may remain undetectable. Owner checks and supplied counts are self-reported. This local evaluator does not close P20, prove M0 native validation, or authorize a merge. The coordinator reviews evidence before recording any gate in the canonical register.

## Independent shader translation warning check

AI4's historical smoke exposed translation-drop warnings even when interval
counters reported zero dropped draws. Reports now count the exact pinned
pipeline.rs message "shader does not translate; its pipelines' draws are
dropped" separately across the entire supplied input, even skipped warmup.
A positive count or unavailable field prevents formal acceptance (insufficient
evidence unless another correctness failure is known). A warning does not
prove a required draw executed or explain an exit. A zero count is merely no
matching message observed: log filtering, missing records, different runtime
versions and earlier initialization outside the measured window may hide
failures. Retain and review startup logs locally as part of operator checks.
Never infer correctness from interval counters alone. Only counts are exported;
no warning details, identities, paths or title data. This is a conservative
review gate, not a new runtime telemetry producer or FPS optimization.

## Diagnostic-only observation exclusion (D12)

Every trial now needs the operator check experimental_observation_disabled:
true only if experimental CPU trace, dirty observation, and other added
measurement probes not approved for formal acceptance were disabled.
Existing baseline frame logging remains required. Missing this new check
makes older manifests insufficient until the operator confirms it; never
fill it automatically. A dirty_observe_v1 message in supplied logs, even a
zero or malformed snapshot, also disqualifies the trial as insufficient.
The separate CPU trace file is not detectable in ordinary frame logs; the
operator must verify flags and build. Missing observation lines are not proof
of disabled instrumentation. Keep diagnostic runs distinct from milestone
runs.

Proposed AI2 #28 41e4cbf5 schema is parsed offline only. Path 0 = selected
copy-back pieces, 1 = card merge, 2 = relay merge. Exact numeric fields with
independent absolute caps (4096 completed samples, 268435456 compared bytes,
65536 chunks and unequal chunks per path), latest row and valid/descending
records per path, malformed count globally. No cross-field constraints due
to independently loaded atomics. No path sums, deltas, ratios, admission or
contention inference. Missing path is unavailable. Chunk is slice-relative
4KiB, not a unique backing page; path 0 biased to selected differences.
All supplied log lines including warmup are inspected; strict payload parser
can reject decorated or version-changed messages. No raw payload exported.
This is schema/acceptance work, not authorization to integrate the producer.

## Pipeline library initialization observation (#37)

AI2 #37 7009627a proposes a failure-only diagnostic with numeric phase
0 (Device1 query), 1 (empty CreatePipelineLibrary), 2 (Library1 query),
and signed i32 HRESULT. Accept the full signed range including zero because
the producer observes Result::Err, not a sign test. Exact payload, bounded
per-phase latest code/count, invalid message count. No driver cause inferred.
Absence may mean disabled, bypass, missing host, success, or missing logs;
it does not prove a library exists. Observations include warmup. Formal
acceptance refuses any marker (including malformed); older report objects
without the field are insufficient. Operator experimental_observation_disabled
must also confirm this probe is disabled. No registration or local launch
authorization follows from schema approval. B003 failure reason still unknown.
