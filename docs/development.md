# Emulard

Experimental compatibility-layer development tools for x86-64 runtimes and graphics translation. This repository contains source-only development utilities, not a standalone emulator.

## Current milestone

- Revision-pinned candidate for per-command-list raw GPU memory synchronization.
- Three embedded Rust regression cases for interleaving, write tracking, and reset.
- Python patcher tests and a read-only Linux compatibility preflight.

## Usage

Run the local probe:

```sh
bash tools/preflight.sh
```

Run patcher unit tests:

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
```

The patcher targets the reviewed public [upstream implementation](https://github.com/fxceless/victory-fork). Use a separate local checkout, never modify the upstream remote. The exact source blobs are pinned in the script. Dry-run by default; explicitly pass `--apply` to edit the local checkout.

```sh
python3 tools/apply_memory_patch.py /path/to/checkout
python3 tools/apply_memory_patch.py /path/to/checkout --apply
```

Review the resulting diff and test using the supported Windows Rust toolchain:

```sh
cargo test -p victory-gpu raw_copy_progress_tests --locked
cargo test -p victory-gpu --locked
```

## Scope and verification

The candidate replaces global copy-count sampling with per-list read/write high-water marks. It assumes an append-only copy registry. This does not resolve all GPU memory coherence, submission ordering, descriptor lifetime, missing-page, or graphics translation issues. Source locations were verified against the reviewed upstream blobs; Windows compilation, GPU execution and Linux runtime compatibility are unverified.

No proprietary assets, executables, credentials, personal reports or user-specific configuration belong in this repository. Keep local diagnostic outputs out of version control. The patcher and regression code are GPL-3.0-or-later; upstream licensing and notices remain applicable to any modified checkout.
