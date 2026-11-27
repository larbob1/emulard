# Claims and handoffs

Use your workstream issue (#11 memory, #12 graphics, #13 reliability, #27 local validation) as append-only communication. Read all four issues before touching overlapping symbols. For chat replacement use [START-HERE.md](START-HERE.md). Record checkpoints after substantive milestones, not only at the end of a session, so a replacement can recover even if a conversation ends unexpectedly. Coordinator summarizes important changes here; don't independently edit this file.

## Claim template
- Role / P-ID / concrete task:
- Base SHA / working branch:
- Files and prepared upstream functions/anchors:
- Shared dependency or conflict:
- Test plan / expected evidence:

## End-of-session handoff
- Role / P-ID / status (candidate, prototype, blocked, validated; resolved only by acceptance):
- Commit SHA / draft PR / base SHA:
- Changes and actual old/new behavior:
- Tests run, pass/fail counts, CI link; unrun tests:
- Performance measurements or "unmeasured":
- Shared changes requested / blockers:
- Exact next action and remaining work:

Current handoff: memory owns PR #9/#10; graphics and reliability may begin their first assignments independently. No automatic communication or background work.

## AI 1 latest handoff
P04/P08/P10: candidate 49ca476, PR #10. Native test-only pinned read fixture committed; latest CI pending. P05 PR #9 native passed at 72fcda9. Earlier software replay native passed at 2465f0a. Next: verify new fixture and mirror native results, audit read-only consumer and synchronization contracts with graphics before changing production reads. No other agent branch touched; performance unmeasured.

## AI 1 coordinated handoff
P07 PR #16 at 1f5cbf1; synthetic checks passed; native pending. P04/P10 pinned native read still pending; requested graphics agreement on GPU synchronization before production consumer work. Requested AI 3 report allowlist for scatter counters. AI 2 PR #14 and AI 3 PR #15 opened independently; coordinator review and owner merge approval outstanding. No cross-branch changes.

## Coordinator combined-build handoff
PR #18, dbac4c6, exact snapshots #9/#14/#15; see status for CI. Other branches continue independently; no merge approved. Next: review combined native result, compare individual switches on owner hardware, then review newer agent PRs. All 24 IDs open.

## AI 1 handoff: refreshed reverse index
P05/P08 PR #19 b8af047; source change isolated, native validation pending. Reconcile against combined runtime only after checks and actual alias churn measurements. AI2/AI3 claims disjoint; no synchronization change. Continue native validation review, not blind integration. All IDs open.

## AI 1 handoff — P12
PR #20 ed67056: six standalone generation tests and synthetic suite pass. Mirror #10 at 3803f32 native passed 31 suites + both profiles; direct read fixture still running. P12 has no runtime consumers. Next: audit mutation footprints and synchronization, await native checks and owner gameplay evidence. No branch merges or other agent edits.

## AI 1 handoff — storage lookup
PR #21 39a481d, opt-in lookup optimization, native pending; synthetic pending. AI2 narrow staging work approved; AI3 CPU trace plan requested. Preserve frozen #18 and source branches. Measure actual workloads before integration. All IDs open.

## Coordinator handoff — native graphics validation
PR #22 b183b12 validates frozen #14/#17 snapshots independently; CI synthetic pending, native active. Scatter #16 native passed 29 suites + both builds. #18 unchanged; no source branches merged. Next: review native outcomes and obtain matched Proton measurements. All IDs open.

## Replacement coordinator handoff
P05 #25 7f7db1e synthetic passed 115 Python +4 range +6 hint +10 portable copy executions, native deferred; P21/P24 #23 c074896b synthetic passed 135 Python +4 standalone +10 portable copy executions, native active. #18/#19/#10/#21/#22 native passed (see STATUS for counts/links). #18 frozen, no merge. AI2 contract posted #12, AI3 review posted #13; all production synchronization restricted pending writer/lease/lock-order review. Next: finish #23, schedule #25 native, review exact P10 backing consumers and P12 writer publication, obtain owner matched Proton test from #18 before stacking more unmeasured candidates. All 24 IDs open; performance unmeasured.

### P10/P12 handoff
#26 47ec512 test-only alias proof, initial compile error fixed; synthetic job passed 114 Python/17 standalone Rust, portable prep final pending; schedule native after current jobs. #25 0e48e3b native active alongside #23. Existing MANY_VIEWS omissions prevent use as exact footprint; remap lock is not data writer lock. Next audit complete live mutation domains, implement synchronized publication design with AI2, review actual mapping performance data and get frozen #18 Proton smoke. No merge or gameplay result.

### AI4 workstream
AI4 #27 assigned local evidence collection, with read-only title isolation, supervised baseline and frozen #18 candidate order; first loading-only smoke and build blocker recorded in BENCHMARKS. Native #23 42/42 groups passed, final #26 portable job passed. Next local gameplay validation and review exact AI2/AI3 proposed hooks; no new FPS result.

#26 native scheduled on acfd8375, #23 completed, #25 active. D12 diagnostic staging gates provided to AI2 and AI3; exact full prepared composition and registration still need review. AI4 longer smoke underway per issue claim, not a result. No game files or main/frozen branches changed by coordinator.

### Single-variable storage candidate
#29 15778831 derives from frozen #18 and exact #21 lookup patcher/test. Native #25 verified 34/34; #29 synthetic passed 160 executions and pinned prep, native active; #26 active. AI4 initial test order unchanged, optional storage comparison after valid #18 gameplay and clearance. Next: local baseline, native #26/#29, #17 extent snapshot, prepared diagnostic review. No merge/gameplay result.

### P16/P03/P13/P14 follow-up
#30 de34a244 native active, synthetic passed; #31 be1e4003 exact prepared preview checks passed both jobs. Caller/feature/schema review remains, no production registration. AI4 historical loading/menu exit 3, translator warnings; approved local toolchain in place, exact #18 build in progress per report. Prioritize verified rendering before measuring optimization. Review #26/#29/#30 native and actual #18 launch; texture preparation lead needs matched evidence. No merges or gameplay result.

#32 review-only short-lock publication proposal; prepared anchors passed. Do not enable or register until AI2 staging/lock/fence review and native race tests. Continue #18 actual rendering validation and native #26/#29/#30; AI2 threaded retry snapshot after current jobs. No new gameplay evidence.

#26 native passed; #33 isolated native CPU trace staged and synthetic passed, native pending. B003 exact #18 reached first cutscene but stopped safely for low available RAM; no gameplay acceptance. Next offline memory/pipeline/remap phase analysis, native #29/#30/#33, review bounded safe local test plan. No new gameplay performance claim.

B003 offline evidence narrows host-copy windows/retention; request existing ownership/coverage values, hold further runs. #29 native passed; #34 isolated scatter composition portable passed, native and synthetic regression pending at check. Next investigate descriptor/heap/inflight retention and safe bounded plan after evidence, check #30/#33/#34 native. No verified gameplay.

#30 native passed; #34 synthetic passed, #33/#34 native active. #36 exact #35 preview passed, not release approval. B003 holder evidence requires independent list/slot/fence ownership before cleanup; request actual skipped-refresh/heap-drop/replay fixtures and numeric pipeline library creation failure review. Hold local runs/switches. No new FPS result.

D17 owner authorizes bounded protected local testing; #27 7210804163 immediate frozen #18 control, existing RAM guard and read-only isolation, no repeated approval within scope. #33 summary filter corrected, native rerun; #38 library initialization native candidate synthetic passed. Next check local control/phase metrics and native #33/#34/#38; diagnostic-only approved after explicit evidence and safe plan. No ownership-release approval or FPS result.

#34 native passed 42/42; #39 test-only smaller-window geometry validation active. #33/#38 native active. D17 local #18 authorized, awaiting result. Review actual #35 ownership fixture (observation-only), native grid and descriptor gate before bounded single-setting 4096/2048 trial; no unapproved release or default changes. No new gameplay FPS.

B004 #18 repeated cutscene start, rapid RAM decline stop, no verified gameplay or matched improvement; D17 still permits bounded testing when comparable headroom restored. #40 exact 30-case CPU native gate scheduled, original #33/#38/#39 active. Next check native results, local readiness and actual memory/descriptor evidence; no immediate retry/toggle or unapproved eviction.

### AI1 recovered session — P10/P15/P24
Read-only claim #11 7211083504. B005 exact #18 all-off pressure stop despite recovered headroom, no gameplay, phase-attribution gap. #40 exact CPU trace 30/30 and both builds passed; #33/#38 native labels and both profiles passed; #39 native all groups failed with sanitized root diagnostic absent, source prep/toolchain passed. No source changes or new launches. Coordination requests #27 7211089626, #13 7211089989, #12 7211090386. Next: offline B005 attribution; isolate sanitized #39 build failure root, exact #35 prepared composition/ignored WARP one-case native validation, review diagnostic path/overhead before any launch. All IDs remain open, performance unmeasured, no merge.
