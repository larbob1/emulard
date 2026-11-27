# Getting started with Emulard

This guide is for people who are new to the project. Emulard is still experimental, and no ordinary installation package is available. If you only want to play games, check the [releases page](https://github.com/larbob1/emulard/releases) for future releases instead of building unfinished development code.

## Before testing

- Use a 64-bit PC with a compatible graphics driver. Windows builds are experimental; Linux uses Wine/Proton, not a native Linux executable.
- Keep a known-working setup separate from experimental builds. Use a dedicated Wine prefix if testing on Linux.
- Use only trusted executable files and software you are authorized to test. No game files, keys or proprietary runtime binaries are provided here.
- There are no confirmed minimum hardware specifications or verified compatibility list yet.

## How to try a development build

Source code is available on the [performance development branch](https://github.com/larbob1/emulard/tree/dev/performance-phase6). Main is the documentation homepage, not the runtime. Building requires Git, Python, Rust and the platform's development tools.

Follow the [developer build guide](DEVELOPMENT.md) if you are comfortable compiling software. The [first-launch guide](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/first-launch.md) explains the smoke checks that must pass before launching local software. Do not use an executable simply because it has an .exe extension or skip those checks.

If you already have a known-working development build, do not replace it. See the [short performance test guide](PLAYTEST.md) to compare experimental settings using the same scene and build.

## Report an issue

Open a [GitHub issue](https://github.com/larbob1/emulard/issues) and include your OS, CPU, GPU, RAM, runtime revision, whether the game launched, whether the world and controls worked, and approximate FPS. Describe what happened before a crash. Share only reviewed numeric reports, not raw logs, local file paths, keys or game files.

For developers, the [30 FPS roadmap](ROADMAP-30FPS.md) and [documentation index](README.md) explain the work in progress.
