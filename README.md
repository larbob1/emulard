# Emulard

**An experimental project working toward playing compatible console games on a PC.**

Emulard builds on [VIctory](https://github.com/fxceless/victory-fork) and is working to improve game compatibility, graphics and performance on Windows and Linux through Wine/Proton.

> **Early development:** Emulard is not ready for everyday gaming. There is no stable, ready-to-install release yet. Some games may fail to launch, show incorrect graphics, run slowly or crash.

## What can it do today?

| Feature | Current status |
| --- | --- |
| Windows | Experimental |
| Linux (Wine/Proton) | Experimental |
| Game graphics | Incomplete; compatibility varies |
| Performance | Approximately 2–3 FPS in an early Proton gameplay test (reported by the project owner) |
| 30 FPS gameplay | Goal, not yet verified |
| One-click installer | Not available |

Our first major goal is **30 FPS with correct graphics and responsive controls**. An early Proton gameplay test reached approximately 2–3 FPS. This is a reported result, not a standardized benchmark or a guarantee that other systems will work.

## Getting started

If you just want to try Emulard, start here:

1. Read the [beginner's testing guide](docs/GETTING-STARTED.md).
2. Check [Releases](https://github.com/larbob1/emulard/releases) for any published builds. At present, this is a source-only project; building the experimental runtime requires developer tools.
3. If you are comfortable testing unfinished software, follow the guide to select an experimental build and run a local test. Keep your existing working setup unchanged.

You need a compatible 64-bit PC, an up-to-date graphics driver, and your own legally available software to test. A particular GPU or amount of RAM does not guarantee compatibility. Emulard does not include games, keys or proprietary files.

## Frequently asked questions

**Can I download an installer and start playing?**  
Not yet. The source and build instructions are available, but there is no supported consumer installer.

**Which games work?**  
There will only be one.

**Does it run on Linux?**  
Experimental tests use Wine or Proton to run a Windows-target runtime. A native Linux version is not available.

**Is it already running at 30 FPS?**  
No. That is the current development target, and it must be confirmed through real gameplay tests.

**How can I help?**  
If you're comfortable testing, report crashes, missing graphics and performance using the [testing guide](docs/GETTING-STARTED.md). Please do not upload game files, keys or raw private logs.

## Project links

[Getting started](docs/GETTING-STARTED.md) · [Report a problem](https://github.com/larbob1/emulard/issues) · [30 FPS roadmap](docs/ROADMAP-30FPS.md) · [Developer documentation](docs/README.md)

Emulard is an independent project and is not affiliated with any console manufacturer. See the developer guide and upstream source notices for licensing and attribution.
