# Runtime compile validation

The Windows workflow prepares the pinned public runtime in an isolated temporary directory. It builds two configurations: the default patch set and the optional per-dword shader memory candidate. It runs targeted Rust suites for memory scheduling, query result bounds, wave retry policy, and the CPU ray-intersection reference. It then compiles the release runtime and type-checks the diagnostics configuration.

External source, raw logs, and binaries are not published by this workflow. Output consists of stage names, exit status and Rust diagnostic codes. No title assets or user data are needed. The temporary checkout is discarded after the job.

The job is a compilation gate, not a GPU or gameplay test. Hosted Windows does not represent the target graphics device. A successful job does not establish Linux runtime compatibility, correct lighting, or playable performance. If a stage fails, reproduce it in a separate local checkout to inspect the full diagnostic privately.

Local Windows build command:

```sh
python tools/build_runtime.py ../runtime-baseline --build
```

A second isolated candidate can use the same command with a different checkout path and --lighting-memory. Keep the existing builder safety rules enabled. Avoid running unreviewed executables or sharing local configuration and logs.
