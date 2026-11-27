# Starting snapshot — 2026-11-27 UTC

Current user-reported Proton gameplay: 2–3 FPS. Tested commit/flags/scene and numeric logs not yet supplied. No measured gain or formal 5 FPS gate.
Common integration base: 132ee11761cbd250863ea1d267999b3613b5771b (runtime changes at c5db073). Upstream paired revision: 51700c6d43a3507fa65e50fe4bb64074ce706cd4 from fxceless/victory-fork.
- Windows validation passed at 8956a8e and 027849b, 21 selected suites and both profiles. [Preflight CI](https://github.com/larbob1/emulard/actions/runs/45938913428).
- Hot-path isolated 2871877 passed 24 suites and both profiles; opt-in code ported to cumulative c5db073. [Combined CI](https://github.com/larbob1/emulard/actions/runs/45939884795) active at snapshot.
- PR #9 exact placeholders at 72fcda9: 115 Python, 18 standalone/portable Rust executions passed; [native CI](https://github.com/larbob1/emulard/actions/runs/45940202830) active.
- PR #10 software table at 2465f0a: 113 Python, 20 Rust executions passed. Latest 3803f32 adds observational pinned mirror: 114 Python and 24 portable/standalone Rust executions passed; [native CI](https://github.com/larbob1/emulard/actions/runs/45940715720) queued. No production host remaps eliminated.
- Open PRs #1–7 stacked historical/integration, #8 older hotpath source ported (not merged), #9 placeholders, #10 software pages. No merge authorized.
- Graphics and reliability branches created at common base. Agents not yet onboarded; no task claim from either.
Check live [Actions](https://github.com/larbob1/emulard/actions) and [PRs](https://github.com/larbob1/emulard/pulls) each session; this snapshot is not live.

## Latest memory workstream update

- P05: exact-placeholder candidate 72fcda9 passed [Windows CI 45940202830](https://github.com/larbob1/emulard/actions/runs/45940202830), 32 selected suite invocations and both profiles. Isolated, not merged; measured Proton benefit and full authoritative interval tracking remain open.
- P04/P08: software page model 2465f0a passed [Windows CI 45940469770](https://github.com/larbob1/emulard/actions/runs/45940469770), 28 selected suites and both profiles, including native three-way replay. Pinned mirror 3803f32 passed [synthetic CI 45940715753](https://github.com/larbob1/emulard/actions/runs/45940715753), 114 Python tests and 24 standalone/portable Rust executions. Its native CI remains active.
- P04/P10: PR #10 now at 49ca4761a8b917cca2c0b001203c838777cada91. Adds a test-only native read-only backing view fixture: scattered cross-page reads, alias replacement, retained plan after all views/page IDs retire, and final Arc release. No production read callback, mapped-byte pin, GPU synchronization or avoided host remaps. [Synthetic](https://github.com/larbob1/emulard/actions/runs/45941392929) and [native](https://github.com/larbob1/emulard/actions/runs/45941392890) CI started. No new FPS measurement; all 24 IDs remain open.

AI 2/3 branches and issues unchanged with no claim comments at session start; check live issues for new claims. No merge approved.

### Coordinated development update

- Combined cumulative c5db073 passed [Windows CI 45939884795](https://github.com/larbob1/emulard/actions/runs/45939884795): 27 selected suite invocations and both release/diagnostic builds. This is the latest cumulative runtime-changing revision with native acceptance evidence, not a new Proton performance result.
- P07: [PR #16](https://github.com/larbob1/emulard/pull/16), commit 1f5cbf1049d0c76496df77aaa85f0d079527d960, adds opt-in VICTORY_MAP_SCATTER_LOCK_BATCH=1. Bounded ordered changed prefixes (up to 64 pages) amortize mapping lock acquisition while preserving per-page native operations, duplicate order, invalid/clear/unchanged fallback and stop-on-failure. Three exact prepared anchors verified. [Synthetic CI](https://github.com/larbob1/emulard/actions/runs/45941647725) passed 114 Python tests, four range-gate tests, ten portable copy-helper executions and pinned preparation. [Native CI](https://github.com/larbob1/emulard/actions/runs/45941647777) pending. Longer writer holds may hurt readers; no syscall reduction or FPS claim. P07 is a candidate; true host coalescing and measured acceptance remain open.
- P04/P10: pinned-read fixture 49ca476 passed [synthetic CI](https://github.com/larbob1/emulard/actions/runs/45941392929); native fixture remains queued. Production reader work depends on native verification and graphics fence/ownership agreement.
- AI 2 opened [PR #14](https://github.com/larbob1/emulard/pull/14) for P22 pipeline cache publication; AI 3 opened [PR #15](https://github.com/larbob1/emulard/pull/15) for P02/P03/P23 benchmark/reporting. Their changes have not been integrated or independently accepted. Shared ownership requests posted to issues #12/#13. All 24 deferred items remain unresolved; no merge.

### First combined multi-agent playtest candidate

- [PR #18](https://github.com/larbob1/emulard/pull/18), branch dev/performance-phase6-combined-playtest, pinned commit dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1. Isolated review build on 2d244a5, staging PR #9 at 72fcda9 (placeholder hints, native passed), PR #14 at c660257 (pipeline cache publication, synthetic passed), and PR #15 at 9330d96 (reporting/acceptance/storage tools, synthetic passed). Existing files checked for overlap; added exact-placeholder counter/test on combined branch. Other agents have advanced their own heads; those later changes are not included. No source branch merge, deletion or change to main.
- [Combined synthetic CI](https://github.com/larbob1/emulard/actions/runs/45942012900): all jobs passed. [Combined Windows CI](https://github.com/larbob1/emulard/actions/runs/45942012941) started. The branch contains docs/performance-combined-playtest.md with matched comparison instructions. Await full native validation before recommending it for gameplay.
- PR #10 pinned backing reader, PR #16 scatter lock batching and PR #17 pipeline stream bounds are excluded pending native validation/review. All 24 deferred IDs remain unresolved. No measured gain beyond owner-reported 2–3 FPS.

### Reverse-alias index candidate (P05/P08)

- [PR #19](https://github.com/larbob1/emulard/pull/19), commit b8af0471247b038337d15b9682a598db00c9ffb0, branch dev/performance-phase6-alias-index-v2. Refreshes 3b63d02 prototype on latest cumulative 5d0face. HLE and GPU reverse indexes use BTreeSet, changing large-group removal from linear retain to logarithmic removal. Adds native HLE 64-alias churn fixture (32 replacements, exact reverse lookup and actual alias bytes, unmap and free) and GPU independent-view test. Small groups may regress; no cumulative default change, host remap elimination or FPS claim. [Synthetic CI](https://github.com/larbob1/emulard/actions/runs/45942226564) passed; [native CI](https://github.com/larbob1/emulard/actions/runs/45942226390) pending. P05/P08 remain open.
- PR #18 combined native validation still active at check; #10/#16 native checks likewise not yet complete. AI 2 continues shader cache recovery/identity work on #14, AI 3 continues PGO planning and reporting on #15. Read their issue handoffs; no new integration or merge. All 24 deferred tasks remain tracked. No new gameplay measurement.
