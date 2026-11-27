# Short performance test (first comparison)

The purpose of this session is to identify which settings help on real hardware, not to certify 30 FPS. Keep the known-working build and original prefix available. The selected candidate passed all 21 selected Windows test invocations and both build profiles in [Windows CI](https://github.com/larbob1/emulard/actions/runs/45937702602). Proton gameplay remains unverified. Newer commits are being checked separately; use the pinned revision below. If any smoke check, memory test or launch fails, record it and stop that candidate. Do not disable correctness checks.

## 1. Select a build

For a test of the cumulative branch, use a separate integration checkout pinned to commit `8956a8e3a3f847a2e7959ac17623debc11a1da6c`:

```sh
git clone --branch dev/performance-phase6 https://github.com/larbob1/emulard.git emulard-playtest
cd emulard-playtest
git switch --detach 8956a8e3a3f847a2e7959ac17623debc11a1da6c
python3 tools/build_runtime.py ../runtime-playtest --paired-wave-refresh
python3 tools/cross_build.py ../runtime-playtest --diagnostics --jobs 2
```

Linux cross-build needs a configured Rust, cargo-xwin, Clang, LLD and SDK environment. If you already have a local candidate build, use its actual commit and path instead of rebuilding. The fresh build may take longer than the available session; no completed cross-build is guaranteed. Do not compare different build profiles or different commits as a single-switch experiment. Follow [smoke checks](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/first-launch.md) first. Use your known-working Proton adapter, if that is how your previous test ran.

## 2. Run a short matched comparison

The commands below work in Fish or Bash. Replace the three example paths with your actual paths. Keep other settings, render scale, resolution, cache state, scene and camera route fixed. Use the same diagnostic executable for both runs, with capture off. The examples explicitly turn off the new mapping experiments for A and enable only the exact-match optimization for B. Ensure other experimental flags from prior sessions are unset before beginning. A is the same candidate with optimizations off, not the historical compatibility branch.

**A — comparison baseline**

```sh
env WINEPREFIX=/path/to/prefix VICTORY_FRAME_LOG=1 VICTORY_MAP_SKIP_SAME=0 VICTORY_MAP_DIFF=0 VICTORY_MAP_RUNS=0 VICTORY_CACHE_PAGE_PLACEHOLDERS=0 bash tools/run_wine.sh /path/to/victory.exe /path/to/title.exe --console series-s > baseline.log 2>&1
```

**B — exact-match mapping experiment**

```sh
env WINEPREFIX=/path/to/prefix VICTORY_FRAME_LOG=1 VICTORY_MAP_SKIP_SAME=1 VICTORY_MAP_DIFF=0 VICTORY_MAP_RUNS=0 VICTORY_CACHE_PAGE_PLACEHOLDERS=0 bash tools/run_wine.sh /path/to/victory.exe /path/to/title.exe --console series-s > candidate.log 2>&1
```

Close each run normally. Use fresh log names for additional runs (redirection overwrites the named file). If the known-working setup requires other settings, retain them identically in both runs and document them. If A is already unstable, do not move to B. Only after B works, try the range-diff experiment separately by turning `VICTORY_MAP_SKIP_SAME=0` and `VICTORY_MAP_DIFF=1` in a new run. A brief session may only allow one comparison; this is useful preliminary evidence, not final acceptance.

## 3. Collect results

From the pinned development checkout:

```sh
python3 tools/frame_report.py candidate.log --baseline baseline.log --skip 5 --skip-frame-batches 1
```

The report's `fps_milestones` includes 30 FPS. For the newer explicit 30 FPS report, fetch and switch only the separate integration checkout (the compiled runtime is outside it):

```sh
git fetch origin
git switch dev/performance-phase6
python3 tools/frame_report.py candidate.log --baseline baseline.log --skip 5 --skip-frame-batches 1 --target-fps 30
```

The newer reporting script does not change the external runtime binary. `approx_present_fps` estimates the presentation rate from rounded frame times, not verified visible gameplay FPS.

If there are not enough intervals, repeat with a smaller, identical warmup exclusion and report it. Review the numeric output before sharing it. Raw logs stay on your computer. Record whether the full world is visible, the game responds to controls, and there are crashes, drops or missing graphics. Note the tested commit and actual driver/Proton versions.

A faster FPS counter with a black or incomplete scene is not a success. For formal 30 FPS acceptance, see the [roadmap](ROADMAP-30FPS.md). 
