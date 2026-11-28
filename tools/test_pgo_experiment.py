# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pgo_experiment import (TARGET, build_plan, clean_environment, file_hash,
                            perform, profile_inputs, same_identity)


class PgoExperimentTests(unittest.TestCase):
    def test_build_plans_and_separation(self):
        work = Path("/experiment with spaces")
        plans = {s: build_plan(s, work, 2) for s in ("baseline", "thin-lto", "generate", "use")}
        self.assertEqual(len({p[2] for p in plans.values()}), 4)
        for command, _, _ in plans.values():
            self.assertIn("--locked", command)
            self.assertEqual(command[command.index("--target") + 1], TARGET)
        self.assertEqual(plans["baseline"][1], [])
        self.assertIn('profile.release.lto="thin"', plans["thin-lto"][0])
        self.assertEqual(plans["generate"][1], ["-Cprofile-generate=" + str(work / "raw")])
        self.assertIn("-Cprofile-use=" + str(work / "merged.profdata"), plans["use"][1])

    def test_reject_overrides_and_identity_drift(self):
        for env in ({"RUSTFLAGS": "-Copt-level=0"}, {"CARGO_PROFILE_RELEASE_LTO": "fat"},
                    {"RUSTC_WRAPPER": "custom"}, {"RUSTUP_TOOLCHAIN": "nightly"}):
            with self.assertRaises(ValueError):
                clean_environment(env)
        self.assertEqual(clean_environment({"PATH": "local"}), {"PATH": "local"})
        with self.assertRaises(ValueError):
            same_identity({"identity": {"source": "a"}}, {"source": "b"})

    def test_missing_or_empty_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                profile_inputs(root)
            (root / "test.profraw").touch()
            with self.assertRaises(ValueError):
                profile_inputs(root)
            (root / "test.profraw").write_bytes(b"synthetic")
            self.assertEqual(len(profile_inputs(root)), 1)

    def test_staged_experiment_and_artifact_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, work, llvm = base / "runtime", base / "experiment", base / "llvm-profdata.exe"
            root.mkdir()
            llvm.write_bytes(b"fake tool")
            identity = {"source": {"source": "synthetic"}, "toolchain": "synthetic"}
            calls = []
            def runner(command, cwd, env, check):
                calls.append((command, env))
                if command[1] == "merge":
                    Path(command[3]).write_bytes(b"merged")
                else:
                    target = Path(command[command.index("--target-dir") + 1])
                    binary = target / TARGET / "release" / "victory.exe"
                    binary.parent.mkdir(parents=True)
                    binary.write_bytes(str(target.name).encode())
            with patch("pgo_experiment.source_identity", return_value=identity["source"]):
                perform("baseline", root, work, 2, identity, llvm, {}, runner)
                perform("thin-lto", root, work, 2, identity, llvm, {}, runner)
                perform("generate", root, work, 2, identity, llvm, {}, runner)
                with self.assertRaises(ValueError):
                    perform("merge", root, work, 2, identity, llvm, {}, runner)
                (work / "raw" / "train.profraw").write_bytes(b"synthetic")
                perform("merge", root, work, 2, identity, llvm, {}, runner)
                merged = work / "merged.profdata"
                merged.write_bytes(b"tampered")
                with self.assertRaises(ValueError):
                    perform("use", root, work, 2, identity, llvm, {}, runner)
                merged.write_bytes(b"merged")
                result = perform("use", root, work, 2, identity, llvm, {}, runner)
                self.assertEqual(set(result["artifacts"]), {"baseline", "thin-lto", "generate", "merge", "use"})
                self.assertEqual(result["artifacts"]["merge"], file_hash(merged))
                self.assertIn("\x1f", calls[-1][1]["CARGO_ENCODED_RUSTFLAGS"])
                with self.assertRaises(ValueError):
                    perform("use", root, work, 2, identity, llvm, {}, runner)

    def test_failed_build_does_not_publish_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, work = base / "runtime", base / "experiment"
            root.mkdir()
            identity = {"source": "synthetic"}
            def failed(*args, **kwargs):
                raise subprocess.CalledProcessError(1, "cargo")
            with self.assertRaises(subprocess.CalledProcessError):
                perform("baseline", root, work, 2, identity, base / "llvm", {}, failed)
            self.assertFalse((work / "experiment.json").exists())
            with self.assertRaises(ValueError):
                perform("baseline", root, root / "nested", 2, identity, base / "llvm", {}, failed)

    def test_missing_artifact_and_source_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, work = base / "runtime", base / "experiment"
            root.mkdir()
            identity = {"source": "synthetic"}
            with self.assertRaises(ValueError):
                perform("baseline", root, work, 2, identity, base / "llvm", {},
                        lambda *args, **kwargs: None)
            self.assertFalse((work / "experiment.json").exists())
            other = base / "another"
            def runner(command, **kwargs):
                binary = Path(command[command.index("--target-dir") + 1]) / TARGET / "release" / "victory.exe"
                binary.parent.mkdir(parents=True)
                binary.write_bytes(b"synthetic")
            with patch("pgo_experiment.source_identity", return_value="changed"):
                with self.assertRaises(ValueError):
                    perform("baseline", root, other, 2, identity, base / "llvm", {}, runner)
            self.assertFalse((other / "experiment.json").exists())


if __name__ == "__main__":
    unittest.main()
