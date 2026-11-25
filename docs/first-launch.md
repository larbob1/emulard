# First launch readiness

The recommended initial source candidate is commit 71c8936e8cc280a42cdfac2882dfcae3e6313862. Both Windows runtime compile jobs passed for that revision. [Verified runtime workflow](https://github.com/larbob1/emulard/actions/runs/45515044086). This is compilation evidence, not gameplay or Linux compatibility evidence. Newer candidates should remain isolated until their own build and GPU checks succeed.

## Start with synthetic probes

Run the local preflight. Obtain the two synthetic probe executables from a successful synthetic workflow run in this repository, after reviewing the source and workflow. Keep all files local. The probes test basic CPU ABI execution and D3D12 capabilities. Use the same configured Wine environment for both probes and the version check.

```sh
bash tools/preflight.sh
python3 tools/first_launch.py /path/to/probe-directory
```

The second command deliberately returns an incomplete status until a locally built runtime is also supplied. It prints only stage results, not paths or raw logs. It executes only the supplied synthetic probes and optionally the runtime version command. Use trusted files; a PE header check is not a malware check. A timeout is a failure, not permission to continue. It does not manage or terminate other Wine processes.

## Prepare the compiled-in-CI source revision

In a separate clone of this repository, check out the recommended commit, then prepare a fresh external runtime checkout:

```sh
git switch --detach 71c8936e8cc280a42cdfac2882dfcae3e6313862
python3 tools/build_runtime.py ../runtime-first-test
```

On a Windows build host, use --build during preparation instead. For an experimental Linux cross-build, return to the current Emulard checkout and use the new cross-build helper with that prepared runtime checkout. It requires a configured Rust toolchain, cargo-xwin, Clang, LLD and Windows SDK support. It may download normal build dependencies and SDK files through the build tools. It is not yet verified on Linux; no system packages are installed by the helper.

```sh
python3 tools/cross_build.py /path/to/runtime-first-test
```

After a successful local build, run the smoke checks with the executable supplied using --runtime. The Windows native build and the cross-build use different Cargo output directories; select the actual binary from the relevant build.

```sh
python3 tools/first_launch.py /path/to/probe-directory --runtime /path/to/locally-built.exe
```

Only proceed to authorized local software testing after the smoke checks pass. Keep the structure-builder opt-in, wave-wide experiments, and optional lighting memory patches off for the initial baseline test. Record the first failure stage locally before changing settings. If the runtime starts, compare numerical frame summaries for the same scene, including dropped draws. Do not report playability based on a version check or successful compilation. Do not infer correct rendering from a successful version check. No title assets, keys, packages, private reports, or full runtime binaries are distributed in this repository.

## What remains unverified

Wine runtime compatibility, graphics execution, full-world rendering, memory use and frame rate. The existing Windows CI result does not establish that the Linux cross-build works. No unsupported graphics fallback is enabled by these tools.

## Numeric readiness report

For a local run with diagnostic logging enabled, keep the original log on your machine. From the current development checkout:

```sh
python3 tools/readiness_report.py /path/to/local.log --skip 5
```

The report summarizes known shader refusal categories, observed builder readiness and disable events, raw memory fault messages and frame interval medians. It never emits raw diagnostic messages, shader hashes or addresses. It cannot establish that unlogged problems are absent. Pipeline readiness is not evidence of correct structures, shadows or lighting. Share only the reviewed numerical summary if troubleshooting; do not publish raw logs. No runtime launch is performed by this helper.
