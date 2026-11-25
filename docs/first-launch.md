# First launch readiness

The recommended initial source candidate is commit b5b644696cc6119fc4530a2d029ff7eda6162366. Both Windows runtime compile jobs passed for that revision. [Verified runtime workflow](https://github.com/larbob1/emulard/actions/runs/45517064245). This is compilation evidence, not gameplay or Linux compatibility evidence. Newer candidates should remain isolated until their own build and GPU checks succeed.

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
git switch --detach b5b644696cc6119fc4530a2d029ff7eda6162366
python3 tools/build_runtime.py ../runtime-first-test
```

On a Windows build host, use --build during preparation instead. For an experimental Linux cross-build, return to the current Emulard checkout and use the new cross-build helper with that prepared runtime checkout. It requires a configured Rust toolchain, cargo-xwin, Clang, LLD and Windows SDK support. It may download normal build dependencies and SDK files through the build tools. It is not yet verified on Linux; no system packages are installed by the helper.

```sh
python3 tools/cross_build.py /path/to/runtime-first-test --jobs 2
```

The current cross-build helper also accepts `--diagnostics` to build the diagnostic profile, with the binary under `target/x86_64-pc-windows-msvc/diag/victory.exe`. The release executable is under `target/x86_64-pc-windows-msvc/release/victory.exe`. Both commands use an explicit target directory and limit Cargo concurrency to two jobs by default; this is not a total RAM cap. Do not build both profiles unless needed. The optional `--wine` argument to first_launch.py selects the same trusted Wine executable that will be used for testing.

After a successful local build, run the smoke checks with the executable supplied using --runtime. The Windows native build and the cross-build use different Cargo output directories; select the actual binary from the relevant build.

```sh
python3 tools/first_launch.py /path/to/probe-directory --runtime /path/to/locally-built.exe
```

Only proceed to authorized local software testing after the smoke checks pass. Keep the structure-builder opt-in, wave-wide experiments, and optional lighting memory patches off for the initial baseline test. Record the first failure stage locally before changing settings. If the runtime starts, compare numerical frame summaries for the same scene, including dropped draws. Do not report playability based on a version check or successful compilation. Do not infer correct rendering from a successful version check. No title assets, keys, packages, private reports, or full runtime binaries are distributed in this repository.

## Launching from the package drive under Wine

After the smoke checks pass, use a dedicated, initialized Wine prefix with
the same D3D12 setup used by the graphics probe.

```sh
WINEPREFIX=/path/to/prefix bash tools/run_wine.sh /path/to/victory.exe /path/to/package/title.exe
```

The launcher maps the title folder as `G:` and starts Victory from that
folder. This lets drive-rooted paths such as `\appdata0.rpf` reach the
package even when title code calls Windows directly. The mapping persists
in this prefix. The launcher refuses to replace an existing mapping to
another folder. Set `WINE` if the smoke checks used a custom Wine executable.

For the local title tested on Linux, select the Series S profile:

```sh
WINEPREFIX=/path/to/prefix bash tools/run_wine.sh \
    /path/to/victory.exe /path/to/package/title.exe --console series-s
```

With this title, system Wine reached graphics initialization in Series S
but later raised the same breakpoint as Series X. An initialized Proton
Experimental prefix under Steam Linux Runtime 4 passed that point in
Series S. To use Proton, set `WINEPREFIX` to the initialized
`compatdata/pfx` directory and set `WINE` to an executable adapter that
forwards its arguments to Proton’s `runinprefix` command.

Emulard's runtime preparation applies the multi-plane PresentX compositor
adapted from [Yaekai's VIctory change](https://github.com/Marvisak/VIctory/pull/211)
and its root-signature and command-list recovery follow-ups. A Series S
title can submit the scene and interface as separate textures. The
compositor blends the interface over the scene and preserves the
single-plane copy path.

## What remains unverified

Full title compatibility under Wine, full-world rendering, memory use and sustained gameplay frame rate. The existing Windows CI result does not establish that the Linux cross-build works. No unsupported graphics fallback is enabled by these tools.

## Numeric readiness report

For a local run with diagnostic logging enabled, keep the original log on your machine. From the current development checkout:

```sh
python3 tools/readiness_report.py /path/to/local.log --skip 5
```

The report summarizes known shader refusal categories, observed builder readiness and disable events, raw memory fault messages and frame interval medians. It never emits raw diagnostic messages, shader hashes or addresses. It cannot establish that unlogged problems are absent. Pipeline readiness is not evidence of correct structures, shadows or lighting. Share only the reviewed numerical summary if troubleshooting; do not publish raw logs. No runtime launch is performed by this helper.

## Baseline-first execution policy

Use the compile-verified source candidate above before attempting optional rendering features. Check the runtime's `run --help` output using the same Wine executable. The CLI distinguishes preparing and binding a lawfully available local executable from running it with the explicit execution option. First test binding alone, with the default unsupported-import trap behavior retained. Do not bypass missing imports, turn on unproven wave-wide barriers, or enable partial builder execution just to get more frames. Keep runtime logs local. Only the numerical readiness summary should be considered for sharing after review.

Build results establish source compilation on Windows, not Wine support. A cross-build error or a failed graphics capability probe is a blocker to investigate, not a gameplay failure. No runtime binary or program data is added here.
