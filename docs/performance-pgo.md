# P18 — isolated release optimization experiment

The pinned paired-wave workspace uses Rust 1.98.1 and release line-table debug info; diag inherits release with the diagnostics feature. ThinLTO and instrumentation-based PGO are optional compiler experiments, not default changes. They cannot remove mandatory mapping, synchronization or rendering costs. Obtain actual CPU/GPU bottleneck evidence before prioritizing production adoption.

This standalone helper is native Windows only. It does not modify shared build scripts, Cargo.toml, runtime source or CI. Use a separately prepared pinned paired-wave runtime checkout, an entirely new experiment directory outside it, the pinned native MSVC Rust toolchain and the existing Windows SDK/build prerequisites. Install the matching rustup llvm-tools component separately if not already available. Use a clean Cargo configuration (no custom rustflags, profile or compiler wrappers). The helper rejects common environment overrides; arbitrary global Cargo config, linker/SDK changes and ignored source files are not fully fingerprinted. Keep the machine and toolchain fixed.

From the integration checkout, with paths adapted locally:

    python tools/pgo_experiment.py baseline ../runtime-perf6 ../pgo-session
    python tools/pgo_experiment.py thin-lto ../runtime-perf6 ../pgo-session
    python tools/pgo_experiment.py generate ../runtime-perf6 ../pgo-session

Each build uses a separate target directory with an explicit Windows target, --locked and --release. Baseline is the default release profile for this explicit-target experiment. ThinLTO changes only the release LTO option. PGO generation/use use the baseline profile, not ThinLTO. Do not combine experiments initially. Do not use the instrumented binary for FPS comparisons.

Training: run the generated executable (generate/x86_64-pc-windows-msvc/release/victory.exe under the experiment directory) using the normal authorized local workload and configuration. Use representative gameplay and multiple scenes; exit normally to flush profiles. Set LLVM_PROFILE_FILE to an absolute path in the experiment's raw directory with a distinct filename pattern such as %p-%m.profraw if needed. Verify that nonempty raw files exist. Keep profiles local. Do not mix profiles from other binaries/builds. The helper cannot independently verify that training input came from the generated executable or that the workload is representative.

    python tools/pgo_experiment.py merge ../runtime-perf6 ../pgo-session
    python tools/pgo_experiment.py use ../runtime-perf6 ../pgo-session

The helper selects llvm-profdata from the pinned rustc sysroot, checks source/toolchain identity and hashes generated artifacts, refuses stale output directories and empty profiles, and uses an explicit merged profile. A failed stage does not publish success; use a fresh session for a failed/partial build or stale output. Never use mismatched or stale profiles. Inspect compiler warnings about missing functions, stale profile data or failed instrumentation; a produced executable is not evidence that all profile data was used.

## Measure

Compare baseline vs ThinLTO and baseline vs PGO-use separately with three independent matched runs per configuration, including a held-out scene not used for training. Record exact revision, prepared source fingerprint locally, compiler/linker versions, build size and time, CPU utilization, visible FPS, frame tails, drops, crashes and correctness. Use the same release profile/flags/logging across builds. Keep ordinary release available for rollback. Repeat existing runtime suites and native/Proton smoke checks on each candidate before promotion; coordinator must approve any shared build/CI integration. Windows-built candidate binaries may be tested under the owner's known-working Proton setup after validation; Linux cross-compilation and Proton-based profile collection are unverified and are not implemented by this helper. No PGO or LTO speedup is measured here. Synthetic tests exercise orchestration only.

References: Rust compiler book, https://doc.rust-lang.org/rustc/profile-guided-optimization.html ; Cargo configuration, https://doc.rust-lang.org/cargo/reference/config.html .
