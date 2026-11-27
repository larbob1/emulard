# Benchmarks

| Record | Workload | FPS | Evidence |
| --- | --- | --- | --- |
| B000 | Owner's Proton gameplay | 2–3 reported | Revision, settings, scene, duration and frame logs not provided |
| B001 | Historical diagnostic Proton loading screen only | 25.3–30.1 presentation FPS | AI4 #11 comment 7210504083; 55s timeout exit 124, eight loading intervals 33.2–39.5 ms means, unknown revision, no gameplay, no matched comparison |
| Target | Matched reference workload | 30 | Not achieved |

Use [playtest guide](https://github.com/larbob1/emulard/blob/main/docs/PLAYTEST.md) and [roadmap](https://github.com/larbob1/emulard/blob/main/docs/ROADMAP-30FPS.md). Record revision, flags, OS/driver, hardware, resolution, scene, cache state, duration, correctly displayed frames, p50/p95/p99, drops and correctness. Keep raw logs local. Report approximate presentation FPS separately. Synthetic checks are correctness evidence, not benchmark results.

B001 is not a gameplay benchmark; B000 remains the unverified owner-reported gameplay reference. #18 exact dbac4c6 preparation passed locally; missing cargo-xwin blocked build. No candidate Proton performance result.
