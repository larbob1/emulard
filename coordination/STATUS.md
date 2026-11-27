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
