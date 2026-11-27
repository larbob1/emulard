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
