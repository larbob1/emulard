# Benchmarks

| Record | Workload | FPS | Evidence |
| --- | --- | --- | --- |
| B000 | Owner's Proton gameplay | 2–3 reported | Revision, settings, scene, duration and frame logs not provided |
| B001 | Historical diagnostic Proton loading screen only | 25.3–30.1 presentation FPS | AI4 #11 comment 7210504083; 55s timeout exit 124, eight loading intervals 33.2–39.5 ms means, unknown revision, no gameplay, no matched comparison |
| B002 | Historical diagnostic Proton loading/menu, unclassified intervals | 3.5–30.1 presentation FPS | AI4 #27 7210565839: exit 3 after ~2 min; 100 shader translation warnings, no verified gameplay; unknown revision |
| B003 | Exact #18 diagnostic Proton startup/first cutscene | ~12.75 presentations/s | AI4 #27 7210674289: 1930 rounded startup samples; p50/95/99 33/207/815ms, low-RAM harness exit 143 after ~2m45s; no verified gameplay |
| B004 | Exact #18 all-off second bounded startup/cutscene control | 15.59 presentations/s | AI4 #27 7210865499; 1774 rounded samples, p50/95/99 33/154/674ms; rapid RAM decline guard exit143 at ~127s; no verified gameplay |
| Target | Matched reference workload | 30 | Not achieved |

Use [playtest guide](https://github.com/larbob1/emulard/blob/main/docs/PLAYTEST.md) and [roadmap](https://github.com/larbob1/emulard/blob/main/docs/ROADMAP-30FPS.md). Record revision, flags, OS/driver, hardware, resolution, scene, cache state, duration, correctly displayed frames, p50/p95/p99, drops and correctness. Keep raw logs local. Report approximate presentation FPS separately. Synthetic checks are correctness evidence, not benchmark results.

B001 is not a gameplay benchmark; B000 remains the unverified owner-reported gameplay reference. #18 exact dbac4c6 preparation passed locally; missing cargo-xwin blocked build. No candidate Proton performance result.

B002 single slow interval 202.5ms texture preparation vs 282.2ms/frame, sampled mean GPU 6.7%; no causal inference or gameplay benchmark. Approved workspace-local toolchain now installed; exact #18 build being attempted.

B003: known-revision local build succeeded, owner observed first cutscene start; peak RSS 12.13GiB, min available .95GiB, sampled device GPU mean 6.45%, three drop intervals; zero matching translator warnings does not establish correctness. Historical B002 different build/stage. Do not repeat prolonged tests or compare switches until memory-pressure triage and safe plan reviewed. No matched gameplay evidence.

B003 offline follow-up #27 7210705368: 17s first-cutscene transition, working set 3637→12430 MiB, private 2566→3191, live host-copy capacity 202→3703, loose windows 28→3000, nonlocal 1001→4309, live staging 342→19 MiB. Categories overlap; no leak/ownership/causal proof. Worst present interval 12637ms, 3455 remaps/9295ms aggregate; overlapping counts not additive. Existing window ownership/coverage telemetry requested; no further launch or switch changes pending review.

B003 ownership follow-up #27 7210742582: late 658/3000MiB live windows all extra Arc holders, 648/2960MiB COM holders, 1199MiB ever copied, 2276MiB union, 4/16MiB unsized, grid 4096KiB. Overlapping rounded capacity, no reclaimable RSS or dead heap attribution. Pipeline library unavailable, sampled queue peak 1196; cause unknown. No rerun.

D17 owner-authorized bounded local testing resumes; #27 7210804163 defines scope and safeguards. No new benchmark observation yet; B003 remains startup/cutscene only. Formal acceptance unchanged.

B004 available RAM 3.51→1.25GiB over three 1s intervals, host swap free 11.63→4.84GiB, last RSS 6.89GiB, VmSwap 1.91GiB; no same-phase late runtime allocation snapshot, no matched improvement. Concurrent host memory confound. B000 owner clarified earlier gameplay reached; revision/settings/visual/input unverified. D17 active; recovered comparable preflight headroom before next bounded control.

B005: AI4 #27 [7211038300](https://github.com/larbob1/emulard/issues/27#issuecomment-7211038300), exact frozen #18 all-off, restored initial available RAM 12.44GiB/free swap 13.92GiB, loading/menu only, rapid decline 3.68→1.67GiB in one second, stop143 ~99s. Peak/last RSS 13.01GiB (shmem/file/anon 6.30/3.88/2.83), process anon swap .07GiB; end free swap 12.90GiB. Last full runtime snapshot predates decline: 5 windows/24MiB, staging17MiB, not late attribution. 1432 rounded startup presents, 17.31/s, mean57.8ms, p50/95/99 33/176/510ms, zero matching warning/drop intervals, sampled GPU6.15%, VRAM3947MiB; 114 detail remaps median map62.65ms/reader wait.55ms. Distinct visible phase, no matched speed, correctness or ownership claim. No repeat or switch pending attribution review. Offline existing evidence request #27 7211089626.
