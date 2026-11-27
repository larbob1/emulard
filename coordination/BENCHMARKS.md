# Benchmarks

| Record | Workload | FPS | Evidence |
| --- | --- | --- | --- |
| B000 | Owner's Proton gameplay | 2–3 reported | Revision, settings, scene, duration and frame logs not provided |
| B001 | Historical diagnostic Proton loading screen only | 25.3–30.1 presentation FPS | AI4 #11 comment 7210504083; 55s timeout exit 124, eight loading intervals 33.2–39.5 ms means, unknown revision, no gameplay, no matched comparison |
| B002 | Historical diagnostic Proton loading/menu, unclassified intervals | 3.5–30.1 presentation FPS | AI4 #27 7210565839: exit 3 after ~2 min; 100 shader translation warnings, no verified gameplay; unknown revision |
| B003 | Exact #18 diagnostic Proton startup/first cutscene | ~12.75 presentations/s | AI4 #27 7210674289: 1930 rounded startup samples; p50/95/99 33/207/815ms, low-RAM harness exit 143 after ~2m45s; no verified gameplay |
| Target | Matched reference workload | 30 | Not achieved |

Use [playtest guide](https://github.com/larbob1/emulard/blob/main/docs/PLAYTEST.md) and [roadmap](https://github.com/larbob1/emulard/blob/main/docs/ROADMAP-30FPS.md). Record revision, flags, OS/driver, hardware, resolution, scene, cache state, duration, correctly displayed frames, p50/p95/p99, drops and correctness. Keep raw logs local. Report approximate presentation FPS separately. Synthetic checks are correctness evidence, not benchmark results.

B001 is not a gameplay benchmark; B000 remains the unverified owner-reported gameplay reference. #18 exact dbac4c6 preparation passed locally; missing cargo-xwin blocked build. No candidate Proton performance result.

B002 single slow interval 202.5ms texture preparation vs 282.2ms/frame, sampled mean GPU 6.7%; no causal inference or gameplay benchmark. Approved workspace-local toolchain now installed; exact #18 build being attempted.

B003: known-revision local build succeeded, owner observed first cutscene start; peak RSS 12.13GiB, min available .95GiB, sampled device GPU mean 6.45%, three drop intervals; zero matching translator warnings does not establish correctness. Historical B002 different build/stage. Do not repeat prolonged tests or compare switches until memory-pressure triage and safe plan reviewed. No matched gameplay evidence.

B003 offline follow-up #27 7210705368: 17s first-cutscene transition, working set 3637→12430 MiB, private 2566→3191, live host-copy capacity 202→3703, loose windows 28→3000, nonlocal 1001→4309, live staging 342→19 MiB. Categories overlap; no leak/ownership/causal proof. Worst present interval 12637ms, 3455 remaps/9295ms aggregate; overlapping counts not additive. Existing window ownership/coverage telemetry requested; no further launch or switch changes pending review.
