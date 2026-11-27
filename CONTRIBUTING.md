# Contributing to Emulard

Emulard is an experimental source-only compatibility-layer integration project. Correctness is required before speed. See the [roadmap](docs/ROADMAP-30FPS.md) and [branch policy](docs/BRANCHES.md).

## Workflow

1. Start from the cumulative development branch and create a scoped branch; do not change the preserved compatibility baseline.
2. Identify the deferred-work ID (P01–P24) or explain the new issue. Inspect the pinned source, add a regression fixture, and keep source anchors exact. Preserve existing fallback behavior unless a tested compatibility change is intended.
3. Test the integration patchers with `python3 -m unittest discover -s tools -p 'test_*.py'`. Run relevant prepared runtime suites and check that test filters actually ran tests. Use the appropriate native Windows/Proton build and report any unavailable validation.
4. Compare performance using matched runs with capture off and stable settings. Review full scene correctness, drops, compiler refusals and memory errors. Do not change synchronization or omit necessary draws merely to increase reported FPS.
5. Open a focused pull request listing affected runtime variant, upstream revision, flags/defaults, test results, benchmark methodology, failure modes and remaining work. Update the canonical deferred register with evidence. Keep unverified performance experiments opt-in.

## Useful issue reports

Include the integration commit, upstream variant, OS/driver/CPU/GPU/RAM, build profile, relevant flags, reproducible steps, expected vs observed results, and sanitized numeric diagnostics. For a performance report, include workload, duration, cache state, visible output, dropped draws, average FPS and frame-time percentiles. Distinguish a build failure, runtime test failure, graphics correctness problem and performance regression.

Never include game assets, keys, executables, credentials, private local paths, raw title logs or captured shader contents in public issues. Keep raw traces and diagnostic inputs local. Share only reviewed summaries and source-only synthetic reproductions.

Respect all upstream licensing and patch attributions. Only use software and data you are authorized to test. See individual source license notices.

## Definition of done

A candidate is not complete until the relevant tests pass, the runtime remains correct, and any claimed performance gain is supported by repeatable measurements. If evidence is missing, record the limitation and leave the task open. Follow the [canonical register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md) for evidence.
