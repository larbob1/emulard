#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated native Windows release/ThinLTO/PGO experiment; opt-in only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PIN = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
RUST = "1.98.1"
TARGET = "x86_64-pc-windows-msvc"
STAGES = ("baseline", "thin-lto", "generate", "merge", "use")
OVERRIDES = ("RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "CARGO_BUILD_RUSTFLAGS",
             "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_RUSTFLAGS", "RUSTC",
             "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER", "RUSTUP_TOOLCHAIN")


def checked_output(args, root):
    return subprocess.check_output(args, cwd=root, stderr=subprocess.DEVNULL)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_identity(root):
    revision = checked_output(["git", "rev-parse", "HEAD"], root).decode().strip()
    if revision != PIN or not (root / "Cargo.lock").is_file():
        raise ValueError("expected separately prepared paired-wave checkout")
    digest = hashlib.sha256()
    digest.update(checked_output(["git", "diff", "--binary", "HEAD", "--"], root))
    # Prepared patchers can create new source files without staging them.
    for name in sorted(checked_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], root).split(b"\0")):
        if not name:
            continue
        path = root / os.fsdecode(name)
        if path.is_symlink() or not path.is_file():
            raise ValueError("unsupported untracked source")
        digest.update(len(name).to_bytes(8, "little"))
        digest.update(name)
        digest.update(bytes.fromhex(file_hash(path)))
    return {"upstream": revision, "prepared_source_sha256": digest.hexdigest(),
            "cargo_lock_sha256": file_hash(root / "Cargo.lock")}


def clean_environment(env):
    if any(env.get(key) for key in OVERRIDES) or any(
            key.startswith("CARGO_PROFILE_") for key in env):
        raise ValueError("remove ambient compiler/profile overrides before experiment")
    return dict(env)


def toolchain(root):
    rust = checked_output(["rustc", "-vV"], root).decode().strip()
    if f"release: {RUST}" not in rust.splitlines() or f"host: {TARGET}" not in rust.splitlines():
        raise ValueError("expected pinned native Windows Rust toolchain")
    cargo = checked_output(["cargo", "--version"], root).decode().strip()
    sysroot = Path(os.fsdecode(checked_output(["rustc", "--print", "sysroot"], root)).strip())
    profdata = sysroot / "lib" / "rustlib" / TARGET / "bin" / "llvm-profdata.exe"
    return {"rustc": rust, "cargo": cargo}, profdata


def build_plan(stage, work, jobs):
    if stage not in ("baseline", "thin-lto", "generate", "use") or not 1 <= jobs <= 64:
        raise ValueError("invalid build stage or job count")
    target_dir = work / stage
    command = ["cargo", "build", "--locked", "--release", "-p", "victory",
               "--target", TARGET, "--target-dir", str(target_dir), "--jobs", str(jobs)]
    flags = []
    if stage == "thin-lto":
        command.extend(["--config", 'profile.release.lto="thin"'])
    elif stage == "generate":
        flags.append("-Cprofile-generate=" + str(work / "raw"))
    elif stage == "use":
        flags.append("-Cprofile-use=" + str(work / "merged.profdata"))
        flags.append("-Cllvm-args=-pgo-warn-missing-function")
    binary = target_dir / TARGET / "release" / "victory.exe"
    return command, flags, binary


def nonempty(path):
    return path.is_file() and path.stat().st_size > 0 and not path.is_symlink()


def same_identity(manifest, identity):
    if manifest.get("identity") != identity:
        raise ValueError("prepared source or toolchain changed; start a fresh experiment")


def profile_inputs(raw):
    if not raw.is_dir() or raw.is_symlink():
        raise ValueError("missing raw profile directory")
    files = sorted(raw.glob("*.profraw"))
    if not files or any(not nonempty(p) for p in files):
        raise ValueError("missing or empty raw profiles")
    return files


def verify_artifact(path, expected):
    if not nonempty(path) or not isinstance(expected, str) or file_hash(path) != expected:
        raise ValueError("missing or modified experiment artifact")


def perform(stage, root, work, jobs, identity, profdata, env, runner=subprocess.run):
    if work == root or work.is_relative_to(root) or root.is_relative_to(work):
        raise ValueError("experiment directory must be separate from runtime checkout")
    state_path = work / "experiment.json"
    if stage == "baseline":
        if work.exists():
            raise ValueError("baseline requires a new experiment directory")
        work.mkdir(parents=True)
        manifest = {"identity": identity, "artifacts": {}}
    else:
        manifest = json.loads(state_path.read_text(encoding="utf-8"))
        same_identity(manifest, identity)
    artifacts = manifest["artifacts"]
    if stage in artifacts:
        raise ValueError("stage already completed; use a new experiment")
    if stage != "baseline":
        _, _, baseline = build_plan("baseline", work, jobs)
        verify_artifact(baseline, artifacts.get("baseline"))
    if stage == "merge":
        _, _, generated = build_plan("generate", work, jobs)
        verify_artifact(generated, artifacts.get("generate"))
        files = profile_inputs(work / "raw")
        merged = work / "merged.profdata"
        if merged.exists() or not nonempty(profdata):
            raise ValueError("stale merged profile or missing pinned llvm-profdata")
        runner([str(profdata), "merge", "-o", str(merged), *map(str, files)],
               cwd=root, env=env, check=True)
        if not nonempty(merged):
            raise ValueError("profile merge did not produce data")
        artifacts[stage] = file_hash(merged)
    else:
        command, flags, binary = build_plan(stage, work, jobs)
        if (work / stage).exists():
            raise ValueError("stage output already exists; avoid stale artifacts")
        if stage == "generate":
            raw = work / "raw"
            raw.mkdir()  # reject stale training data
        elif stage == "use":
            _, _, generated = build_plan("generate", work, jobs)
            verify_artifact(generated, artifacts.get("generate"))
            verify_artifact(work / "merged.profdata", artifacts.get("merge"))
        build_env = dict(env)
        # Explicit target keeps these flags out of host build scripts/proc macros.
        # Set for every experimental build to avoid inheriting ambient RUSTFLAGS.
        build_env["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(flags)
        runner(command, cwd=root, env=build_env, check=True)
        if not nonempty(binary):
            raise ValueError("build did not produce a nonempty executable")
        artifacts[stage] = file_hash(binary)
    # Do not publish state if the prepared source changed during a build.
    if source_identity(root) != identity["source"]:
        raise ValueError("source changed during experiment")
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary.replace(state_path)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error("jobs must be between 1 and 64")
    if sys.platform != "win32":
        parser.error("native Windows only; cross-build/Proton PGO training is not validated")
    root, work = args.checkout.resolve(), args.experiment.resolve()
    try:
        env = clean_environment(os.environ)
        identity = {"source": source_identity(root)}
        identity["toolchain"], profdata = toolchain(root)
        perform(args.stage, root, work, args.jobs, identity, profdata, env)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print("Experiment failed; review local compiler output and prerequisites. No stage accepted.", file=sys.stderr)
        return 1
    print(f"{args.stage}: local artifact verified. No gameplay performance result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
