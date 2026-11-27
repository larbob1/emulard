# Pipeline library initialization diagnostic — P22 isolated candidate

Frozen #18 base `dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1`, pinned upstream `51700c6d43a3507fa65e50fe4bb64074ce706cd4`. B003 offline
logs reported no functioning host pipeline library, no numeric create
error, zero persisted library size. Existing .ok() discards errors;
no conclusion about cause. Duplicate compile gate requires a library
and cannot improve this no-library path.

Diagnostic feature only, explicitly enable
`VICTORY_LIBRARY_INIT_DIAGNOSTICS=1`. Default off. Existing initialization
runs once via OnceLock. No new policy, retries, cache identity changes,
driver calls, success logs, or altered error return. Existing nonempty
blob rejection behavior preserved exactly. No new allocation for disabled
release path; diagnostic opt-in is evaluated during initialization only.

Proposed numeric line:
`pipeline_library_init_v1 phase=1 hresult=-2147467262`
(example synthetic code, not an observed result). Phase 0 = ID3D12Device1
query; 1 = empty CreatePipelineLibrary; 2 = empty library's Library1
query. HRESULT is signed i32 decimal. Absence is not success; host missing,
RenderDoc bypass, valid library and switch off need no new line.
No title, path, shader identifiers, error messages or pointer data.

Three exact anchors verified after 4 worker-tracing hunks and 8
existing library replacements; full prepared runtime and actual Windows
wrapper compilation pending. Four portable helper tests and wiring check.
Native filter library_init_diagnostic_tests, expected four; test both
profiles and actual failure paths if feasible. AI3 schema review and AI1
native/local approval required. Do not launch another prolonged game
test, modify the frozen #18 branch or treat error classification as a fix.
