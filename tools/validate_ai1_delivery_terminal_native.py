# SPDX-License-Identifier: GPL-3.0-or-later
"""Proposed isolated B build gate. No workflow registration or production caller."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASE = "08472987ffee011796d48d7c90114439a6a68908"
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
FIXTURE = "ba754cae4478275ffc6e1450aba5586f66bef9e3"
RUNNER = "10be67f1810ed2d959f147e52d5b488b8af9bd4a"
TARGET = "x86_64-pc-windows-msvc"
TOOLCHAIN = "1.98.1-" + TARGET
CORE = "tools/prepare_ai6_delivery_terminal_preview.py"
NATIVE = "tools/prepare_ai6_delivery_terminal_native.py"
PARENT = "tools/run_delivery_terminal.py"
SELF = "tools/validate_ai1_delivery_terminal_native.py"
BUILDER = "tools/build_runtime.py"
LIB = "crates/victory-gpu/src/lib.rs"
MODULE = "crates/victory-gpu/src/delivery_terminal.rs"
PINS = {
    CORE: (FIXTURE, "0987a77453a850d6f91214324b4724a1a548a4ef"),
    NATIVE: (FIXTURE, "01b4d9ae6be0dcb182c4c0e4b28d64e18a2a9bab"),
    "patches/ai6-delivery-terminal-preview.patch": (FIXTURE, "5342aa50c85b607977e25fbcb1fc7c58d4445054"),
    "probes/ai6_delivery_terminal_native.rs": (FIXTURE, "c68ea7d17541a4d5ffc3c5e178016b06299cd1f0"),
    "docs/ai6-delivery-terminal-preview.md": (FIXTURE, "a16125fa1e6d73c0cd5e82086df0423216e25b90"),
    "docs/ai6-delivery-terminal-native.md": (FIXTURE, "66af1985f6c84d37d2e2fa7ea7e05675160d9b76"),
    PARENT: (RUNNER, "928c508019e984f5b044e021ac0f87c57a45495d"),
    BUILDER: (BASE, "31bc201ad006b304542e8b03405c1a9090d76804"),
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def env():
    prefixes = ("GIT_", "VICTORY_", "RUST_TEST_", "RUSTC", "RUSTFLAGS",
                "CARGO_", "RUSTUP_", "AI0_", "AI1_", "AI2_", "AI3_",
                "AI4_", "AI5_", "AI6_")
    keep = {"CARGO_HOME", "RUSTUP_HOME"}
    result = {k: v for k, v in os.environ.items()
              if k.upper() in keep or not k.upper().startswith(prefixes)}
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    return result


def run(args, cwd, timeout, capture=False):
    args = [str(a) for a in args]
    try:
        p = subprocess.run(args, cwd=cwd, env=env(), timeout=timeout,
                           capture_output=capture)
    except subprocess.TimeoutExpired as exc:
        print(f"timeout command={args[0]} stdout={exc.stdout!r} stderr={exc.stderr!r}", flush=True)
        raise
    if p.returncode:
        if capture:
            print(f"command failed stdout={p.stdout!r} stderr={p.stderr!r}", flush=True)
        raise subprocess.CalledProcessError(p.returncode, args)
    return p.stdout if capture else None


def git(root, *args):
    return run(["git", *args], root, 120, capture=True)


def verify_checkout(expected):
    need(re.fullmatch(r"[0-9a-f]{40}", expected), "expected head required")
    need(git(ROOT, "rev-parse", "HEAD").decode().strip() == expected, "wrong candidate head")
    need(git(ROOT, "merge-base", BASE, expected).decode().strip() == BASE, "wrong integration ancestry")
    expected_paths = set(PINS) - {BUILDER} | {SELF}
    raw = git(ROOT, "diff", "--name-status", "--no-renames", BASE, expected)
    rows = raw.decode("utf-8").splitlines()
    need(set(rows) == {"A\t" + p for p in expected_paths} and
         len(rows) == len(expected_paths), "unexpected composition delta")
    need(git(ROOT, "status", "--porcelain", "--untracked-files=all") == b"",
         "dirty candidate checkout")
    for path, (ref, pin) in PINS.items():
        observed = git(ROOT, "show", f"{ref}:{path}")
        exact = blob(observed)
        need(exact == pin, "reviewed pin mismatch: " + path)
        need(blob(git(ROOT, "show", f"HEAD:{path}")) == exact, "candidate pin mismatch: " + path)
        need(blob((ROOT / path).read_bytes().replace(b"\r\n", b"\n")) == exact,
             "worktree pin mismatch: " + path)
    print(f"candidate_head={expected} integration={BASE} fixture={FIXTURE} runner={RUNNER}", flush=True)


def ordinary(path, directory):
    need(path.resolve(strict=True) == path, "noncanonical path")
    for p in (*reversed(path.parents), path):
        info = p.lstat()
        need(not p.is_symlink() and not p.is_junction() and
             not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT,
             "linked or reparse path")
        if p == path and not directory:
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "nonregular or aliased file")
        else:
            need(stat.S_ISDIR(info.st_mode), "nonordinary directory")
    return path


def sha256(path):
    with ordinary(path, False).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def snap(core, runtime, identity):
    need(core.root_identity(runtime) == identity, "runtime identity changed")
    inv = core.inventory(runtime)
    need(core.root_identity(runtime) == identity, "runtime identity changed")
    return inv


def inv_digest(inv):
    return hashlib.sha256(json.dumps(inv, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def prepare(runtime, core):
    run([sys.executable, "-B", ROOT / BUILDER, runtime, "--paired-wave-refresh"], ROOT, 900)
    ordinary(runtime, True)
    identity = core.root_identity(runtime)
    before = snap(core, runtime, identity)
    old = before
    for path, delta in ((CORE, {LIB, MODULE}), (NATIVE, {MODULE})):
        cmd = [sys.executable, "-B", ROOT / path, runtime]
        run(cmd, ROOT, 120)
        need(snap(core, runtime, identity) == old, "preparer dry changed source")
        run(cmd + ["--apply"], ROOT, 120)
        new = snap(core, runtime, identity)
        changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
        need(changed == delta and old.keys() <= new.keys(), "unexpected preparer delta")
        if path == CORE:
            need(set(new) - set(old) == {MODULE}, "unexpected added path")
            need(blob((runtime / MODULE).read_bytes()) == "912d6f3a972d0ce6067ee31db30069fcb32a6c8a",
                 "core module pin")
        else:
            need(old.keys() == new.keys(), "native added unexpected path")
        need(blob((runtime / LIB).read_bytes().replace(b"\r\n", b"\n")) ==
             "bfa6093d3df202ef0eca4d855d86bb424cc47f30", "lib pin")
        print(f"preparation_receipt path={path} changed={len(changed)} entries={len(new)} "
              f"inventory_sha256={inv_digest(new)}", flush=True)
        old = new
    need(blob((runtime / MODULE).read_bytes()) == "88abde5c80dab3a95de9e9c2986c3b17dc51185f",
         "final module pin")
    need(git(runtime, "rev-parse", "HEAD").decode().strip() == UPSTREAM, "wrong upstream")
    git(runtime, "diff", "--check")
    need(snap(core, runtime, identity) == old, "source changed after preparation")
    return identity, old


def cargo(runtime, *args, timeout=120):
    return run(["rustup", "run", TOOLCHAIN, "cargo", *args], runtime, timeout, capture=True)


def package_identity(runtime):
    rust = run(["rustup", "run", TOOLCHAIN, "rustc", "-vV"], runtime, 120, capture=True).decode("ascii")
    need("release: 1.98.1" in rust.splitlines() and ("host: " + TARGET) in rust.splitlines(),
         "wrong compiler identity")
    version = cargo(runtime, "--version").decode("ascii").strip()
    need(re.fullmatch(r"cargo 1\.98\.1(?: .*)?", version), "wrong Cargo version")
    meta = json.loads(cargo(runtime, "metadata", "--locked", "--no-deps", "--format-version", "1"))
    expected_manifest = runtime / "crates/victory-gpu/Cargo.toml"
    found = [p for p in meta["packages"] if p["name"] == "victory-gpu" and
             Path(p["manifest_path"]).resolve(strict=True) == expected_manifest]
    need(len(found) == 1 and found[0]["id"] in meta["workspace_members"], "GPU package identity")
    targets = [t for t in found[0]["targets"] if t["name"] == "victory_gpu" and
               t["kind"] == ["lib"] and t["test"] is True and
               Path(t["src_path"]).resolve(strict=True) == runtime / LIB]
    need(len(targets) == 1, "GPU library target identity")
    print(f"toolchain={TOOLCHAIN} target={TARGET} cargo={version} rustc={rust!r}", flush=True)
    return found[0]["id"], targets[0]


def select_artifact(raw, package, target, output, profile):
    objects = [json.loads(line) for line in raw.splitlines()]
    finished = [o for o in objects if o.get("reason") == "build-finished"]
    need(len(finished) == 1 and finished[0].get("success") is True, "missing successful Cargo finish")
    found = [o for o in objects if o.get("reason") == "compiler-artifact" and
             o.get("package_id") == package and o.get("target") == target and
             o.get("profile", {}).get("test") is True and o.get("executable")]
    need(len(found) == 1 and found[0].get("fresh") is False, "expected one freshly built GPU test artifact")
    need("diagnostics" in found[0].get("features", []), "diagnostics not compiled")
    binary = ordinary(Path(found[0]["executable"]), False)
    expected_dir = output / TARGET / profile
    need(expected_dir in binary.parents and binary.suffix.lower() == ".exe", "wrong profile artifact root")
    return binary


def build(runtime, output, profile, package, target, inventory_pin):
    need(not output.exists(), "output root already exists")
    output.mkdir()
    ordinary(output, True)
    args = ["test", "--locked", "-p", "victory-gpu", "--lib", "--features", "diagnostics",
            "--target", TARGET, "--target-dir", str(output), "--no-run", "--message-format=json"]
    if profile == "release":
        args.append("--release")
    raw = cargo(runtime, *args, timeout=2400)
    exe = select_artifact(raw, package, target, output, profile)
    identity = sha256(exe)
    print("build_receipt " + json.dumps({"profile": profile, "package": package,
          "target": TARGET, "toolchain": TOOLCHAIN, "args": args, "executable": str(exe),
          "sha256": identity, "prepared_inventory_sha256": inventory_pin}, sort_keys=True), flush=True)
    return exe, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    ns = parser.parse_args()
    need(sys.platform == "win32" and sys.version_info >= (3, 12), "Windows Python 3.12+ required")
    verify_checkout(ns.expected_head)
    sys.dont_write_bytecode = True
    import prepare_ai6_delivery_terminal_preview as core
    run([sys.executable, "-B", ROOT / PARENT, "--self-check"], ROOT, 120)
    with tempfile.TemporaryDirectory(prefix="ai1-delivery-terminal-") as tmp:
        owned = Path(tmp).resolve(strict=True)
        ordinary(owned, True)
        need(ROOT not in owned.parents and owned not in ROOT.parents and ROOT != owned,
             "scratch root overlaps candidate")
        runtime = owned / "runtime"
        identity, prepared = prepare(runtime, core)
        pin = inv_digest(prepared)
        package, target = package_identity(runtime)
        need(snap(core, runtime, identity) == prepared, "metadata changed source")
        receipts = []
        for profile in ("debug", "release"):
            output = owned / profile
            exe, digest = build(runtime, output, profile, package, target, pin)
            need(snap(core, runtime, identity) == prepared, "build changed source")
            receipts.append((profile, output, exe, digest))
        args = [sys.executable, "-B", ROOT / PARENT, "--runtime", runtime]
        for profile, output, exe, digest in receipts:
            args.extend(["--" + profile, exe, "--" + profile + "-root", output,
                         "--" + profile + "-sha256", digest])
        for _, _, exe, digest in receipts:
            need(sha256(exe) == digest, "executable changed after build")
        result = run(args, runtime, 540, capture=True)
        print(result.decode("ascii", errors="strict"), end="", flush=True)
        lines = result.decode("ascii").splitlines()
        need(lines.count("runner_complete profiles=2 cases=4") == 1 and
             lines[-1] == "runner_complete profiles=2 cases=4", "missing final parent receipt")
        expected = [(profile, case, digest) for profile, _, _, digest in receipts
                    for case in ("prearm", "terminal")]
        observed = [tuple(m.groups()) for line in lines if (m := re.fullmatch(
            r"case_accepted profile=(debug|release) case=(prearm|terminal) sha256=([0-9a-f]{64}) .*", line))]
        need(observed == expected, "wrong accepted case identities/order")
        for _, _, exe, digest in receipts:
            need(sha256(exe) == digest, "executable changed after parent")
        need(snap(core, runtime, identity) == prepared, "source changed during parent")
        verify_checkout(ns.expected_head)
    print("gate_complete profiles=2 cases=4 scope=isolated-terminal-fixture", flush=True)


if __name__ == "__main__":
    main()
