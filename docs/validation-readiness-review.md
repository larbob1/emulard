# Validation readiness — reviewer checklist

Scope: P01 / P19 / P24. This is a supplementary reviewer aid, not an authorization, canonical acceptance register, or replacement for the roadmap. Always consult the live [decisions](https://github.com/larbob1/emulard/blob/coordination/coordination/DECISIONS.md), [deferred register](performance-deferred.md) and [local workstream #27](https://github.com/larbob1/emulard/issues/27) first. The historical [Phase 6 comparison protocol](performance-phase6.md) describes the eventual measurement method; it does not grant permission to execute it.

## Authorization comes before execution

At the reviewed coordination revision [45309248](https://github.com/larbob1/emulard/commit/45309248136cf197a60173b8889e69729fbf3e68):

- D17 historically allowed bounded guarded local controls. D20 restricted repetition following recurring memory pressure; restored idle headroom alone did not establish safety.
- D21–D22 allow the specified title-free preflight/evidence and reporting or design work; they do not authorize a new title run, additional maps collection, guard changes or production release.
- D23 reserves owner-machine access for AI4. Other contributors use isolated title-free work and authorized repository CI only. AI1 owns integration/CI; AI3 owns formal acceptance and reporting.
- D24 is a design review, not permission to run the proposed mapping pilot, implement the output worker or perform a local benchmark. Review exact source seams, repeatability and acceptance criteria before implementation. Do not assume diagnostic overhead is zero.
- D25 allows AI0 independent work in confirmed non-overlapping windows only, with mandatory AI1 exact-head review and an explicit AI4 validation disposition. It grants no additional execution permission.

If authorization is missing, ambiguous or superseded, record HOLD and the missing decision; do not infer permission from a green job, historical guide, or previously authorized launch. Keep the frozen [#18 candidate](https://github.com/larbob1/emulard/pull/18) at dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1 unchanged. Never substitute another build under that identifier. Existing safety guards, read-only title isolation and stop conditions remain in force.

## Evidence levels (not interchangeable)

| Evidence | Establishes | Does not establish |
| --- | --- | --- |
| Synthetic model or patcher tests | Selected modeled invariants or patcher behavior | Actual runtime semantics |
| Pinned source preparation | Exact revision and selected patches compose | Successful native compilation or execution |
| Portable helper tests | Tested extracted helper behavior in the stated modes | Full GPU/runtime integration |
| Native selected suites and builds | Selected actual native behavior and build profiles for that exact candidate | Combined integration, Proton correctness or speed |
| Combined native integration evidence | Tests and profiles for the exact composed candidate | Correct rendering, resource pressure or responsiveness under Proton |
| Authorized local startup/smoke | Observed launch phase and bounded local behavior | Steady-state gameplay |
| Matched correct gameplay | Evidence for the specific hardware/settings/workload and milestone | General compatibility or extrapolation to other builds |

Report missing, failed, skipped, zero-match or ambiguous required suites as such, not as passes. A count of suite invocations plus builds is not a count of unique test cases. Count separately repeated modes, and distinguish fixture/model execution from a native test. Preserve adverse and aborted receipts. Do not add overlapping worker durations or infer critical-path improvement from aggregate totals.

## Review intake (one candidate at a time)

- [ ] Record PR URL, exact head, comparison base, current integration head, pinned upstream revision, build profile, patch order and prepared affected symbols. Check the actual diff and relevant owner claims.
- [ ] Review defaults, fallbacks, guard/synchronization/lifetime behavior and changed invariants; distinguish a test-only fixture from a production implementation.
- [ ] Link exact run and job IDs. Confirm actual checkout, source preparation/toolchain, executed commands, mode, test filter, nonempty expected counts, failures/ignored/skips, and both profiles when required. A run-level success is not sufficient.
- [ ] Compare the exact proposed combination against the individually tested candidates. A changed head, upstream pin, patch order or material composition invalidates applicable earlier evidence until reviewed and revalidated.
- [ ] Record AI1's exact-head decision, relevant owner and AI3 review, and local validation REQUIRED or NOT REQUIRED with rationale. If required evidence is absent or failed, HOLD. AI4 alone may execute authorized local tests.
- [ ] Preserve owner merge authority and AI3 formal acceptance. The reviewer checklist itself closes no P-ID and changes no default.

### Worked receipt: isolated HLE retirement candidate

This is a dated example of reading existing CI, not a combined approval. At review, [PR #61](https://github.com/larbob1/emulard/pull/61) was a draft, head fa186087ad55b706d7c3e20240296a860eeac7d6, one commit ahead of historical parent 6e8c5b3cf7dbc11ddd7c5c109cae98cda7f621d3. Integration observed separately at bbea12cb0b2b29618bf4e410d272fe97b81f4bf7; paired-wave upstream pin in that integration builder is 51700c6d43a3507fa65e50fe4bb64074ce706cd4.

| Existing receipt | Verified observation |
| --- | --- |
| [Native job](https://github.com/larbob1/emulard/actions/runs/46025862994/job/140596974933) | 35 selected test groups + 2 builds = 37 passed validation results; xasync 7, dependent callback 1, reentrant 1, five retirement filters each 1 pass / 0 failures; release and diagnostics builds passed |
| [Synthetic job](https://github.com/larbob1/emulard/actions/runs/46025863025/job/140596974387) | 149 Python tests; 4 standalone range tests |
| [Portable job](https://github.com/larbob1/emulard/actions/runs/46025863025/job/140596974908) | 5 portable copy helper cases passed per mode |

Exact-head checkout and final validation summaries were inspected. Synthetic mocked count/timeout failures are regression test inputs, not failures of the actual native job. This document's author did not independently reconstruct the prepared HLE source or execute the native tests; refer to the [AI1 workstream](https://github.com/larbob1/emulard/issues/11) and [AI6 workstream](https://github.com/larbob1/emulard/issues/46) for source review and exact registration. No production scheduling policy, timing result, combined candidate, Proton behavior or FPS gain follows from these receipts.

## Local evidence and the 30 FPS gate

Use the live [benchmark register](https://github.com/larbob1/emulard/blob/coordination/coordination/BENCHMARKS.md) and [roadmap](https://github.com/larbob1/emulard/blob/main/docs/ROADMAP-30FPS.md). B000 is an owner-reported 2–3 FPS gameplay observation, without a standardized matched receipt. B003–B005 are startup/cutscene/menu observations with memory-pressure stops, not verified gameplay FPS. Do not compare rates across different phases as a speedup, or add overlapping memory categories as unique residency. Existing numeric evidence can inform a bounded attribution plan without a new launch.

If a later local run is explicitly authorized, the acceptance owner and AI4 must use the reviewed exact candidate and protocol: record actual scene correctness, controls, settings/cache state, build identity, duration, displayed frames and latency, warnings/drops, pressure and stop cause. Separate startup and presentation rates from gameplay. A correct scene (M1) precedes performance acceptance. The roadmap's proposed M5 gate is three matched ten-minute steady-state runs averaging at least 30 correctly displayed FPS, p95 <= 50 ms and p99 <= 100 ms, no crash, black scene or known missing required draws, responsive controls. This is a proposed acceptance criterion, not a current result or authorization to run ten minutes.

## Handoff template

Copy this record into the relevant workstream rather than creating a competing canonical register:

```text
P-ID / candidate / exact head / parent / integration / upstream:
Changed paths and prepared symbols / flags and defaults:
Evidence class / run and job / exact mode / expected and observed count:
Passed / failed / skipped / not run / missing evidence:
Correctness and performance claims supported (or unmeasured):
AI1 decision and reviewed exact head/base:
Affected-owner / AI3 review:
AI4 validation REQUIRED or NOT REQUIRED, rationale and evidence:
Owner merge decision / unresolved blockers / next action:
```

All P01–P24 remain open at this review snapshot. Verify the live records before using this checklist; do not edit the canonical register independently.
