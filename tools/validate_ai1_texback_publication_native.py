# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated texture landing native gate; no production registration."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)

def build(target, release):
    args = ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib", "--features",
            "diagnostics", "--no-run", "--message-format=json"]
    if release:
        args.append("--release")
    r = subprocess.run(args, cwd=target, capture_output=True, text=True,
                       errors="replace", timeout=2400, env=clean_env())
    if r.returncode:
        print((r.stdout + "\n" + r.stderr)[-20000:], flush=True)
        raise ValueError("test compile failed")
    artifacts = []
    for line in r.stdout.splitlines():
        obj = json.loads(line)
        if (obj.get("reason") == "compiler-artifact" and obj.get("executable")
                and obj.get("target", {}).get("name") == "victory_gpu"
                and obj.get("profile", {}).get("test") is True):
            artifacts.append(Path(obj["executable"]).resolve())
    if len(artifacts) != 1 or not artifacts[0].is_file() or not artifacts[0].is_relative_to(target.resolve()):
        raise ValueError(f"unexpected test executables: {artifacts}")
    return artifacts[0]

REVIEWED = "8949dd3d2d65d535a45734c03c8b1b1a01977ae7"
PROBE = "probes/ai2_texback_publication_baseline.rs"
PINS = {
    PROBE: "d218a9e1195b6fa0dcebb635c7b60596cfa5e85e",
    "docs/ai2-texback-publication-baseline.md": "97ca57db66ebf6393f5597cfaf1d83775a98beb0",
    "tools/build_runtime.py": BUILDER,
}
SOURCES = {
    "crates/victory-gpu/src/host.rs": ("458d146aedf6f13dac80782d283a048d80e4a931", "88acbb3b2cf550cdf2303685fcc32249f9e46328"),
    "crates/victory-gpu/src/texback.rs": ("3102a4f9ed2f80c86a28fcc5070b855143279574", "3102a4f9ed2f80c86a28fcc5070b855143279574"),
    "crates/victory-gpu/src/watch.rs": ("9cf4bc6d686efc56e8bb65bea49c233ace2f8223", "66ce0fb3d6f3e8b72b2a9efdca04135222c6eb07"),
    "crates/victory-gpu/src/descriptor/host.rs": ("7970fc5f0c3977bde0a81dbcec1a497384b933bc", "13a6d0a94621d4a3609abed26cb07c6b6cc6a989"),
    "crates/victory-gpu/src/copystat.rs": ("2e43271583d232efa5def942d3bdae50b2f1d61e", "2e43271583d232efa5def942d3bdae50b2f1d61e"),
    "crates/victory-formats/src/texture.rs": ("fa719c93953d9e6589c4d2cd27a13d773863c316", "fa719c93953d9e6589c4d2cd27a13d773863c316"),
}
MANIFESTS = {
    "crates/victory-gpu/Cargo.toml": "e6d844522016d5bb476dc04ad972b0e0498d7c86",
    "Cargo.toml": "4e21b692d66103d990003164b6f1e4f700bc4086",
}
DEST = "crates/victory-gpu/src/texback.rs"
POST = "2aa089f24763670b7154d0fb3632ddaae5816ec9"
NAME = "texback::ai2_publication_baseline::actual_land_publication_baseline"

def lf(data):
    return data.replace(b"\r\n", b"\n")

def clean_env():
    return {k:v for k,v in os.environ.items()
            if not k.upper().startswith(("VICTORY_", "RUST_TEST_", "AI2_", "AI6_"))
            and k.upper() not in ("CARGO_TARGET_DIR", "CARGO_BUILD_TARGET_DIR")}

def inventory(root):
    result = {}
    def walk(directory):
        for p in sorted(directory.iterdir()):
            rel = p.relative_to(root).as_posix()
            if rel == ".git":
                continue
            if p.is_symlink() or p.is_junction():
                raise ValueError("unexpected link in disposable checkout: " + rel)
            if p.is_dir():
                result[rel] = ("dir",)
                walk(p)
            elif p.is_file():
                with p.open("rb") as f:
                    result[rel] = ("file", hashlib.file_digest(f, "sha256").hexdigest())
            else:
                raise ValueError("unexpected path type: " + rel)
    walk(root)
    return result

def direct(args, target, env):
    try:
        p = subprocess.run(args, cwd=target, env=env, capture_output=True,
                           text=True, errors="replace", timeout=60)
    except subprocess.TimeoutExpired as exc:
        for label, stream in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            print(label + " (partial):", flush=True)
            if stream:
                print(stream.decode("utf-8", errors="replace") if isinstance(stream, bytes) else stream, flush=True)
        raise
    print("stdout:\n" + p.stdout, flush=True)
    print("stderr:\n" + p.stderr, flush=True)
    return p

def run_exact(exe, target, release, mode):
    profile = "release" if release else "debug"
    env = clean_env()
    flags = {"VICTORY_D3D12_WARP": "1", "VICTORY_SWEEP": "0", "AI2_EXPECT_COPY": mode}
    if mode == "none":
        flags["VICTORY_COPY_MODE"] = "none"
    env.update(flags)
    print(f"profile={profile} mode={mode} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(flags, sort_keys=True), flush=True)
    p = direct([str(exe), "--list", "--ignored"], target, env)
    if p.returncode or p.stdout.splitlines().count(NAME + ": test") != 1:
        raise ValueError("exact ignored listing")
    p = direct([str(exe), NAME, "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"], target, env)
    tests = [l for l in p.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in p.stdout.splitlines() if l.startswith("test result:")]
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if p.returncode or tests != [f"test {NAME} ... ok"] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        raise ValueError("missing exact native test receipt")
    rows = [l for l in p.stderr.splitlines() if l.startswith(("publication_adapter", "publication_case"))]
    active = 14 if mode == "normal" else 0
    cases = [
        f"publication_case mode={mode} stale=0 active={active} guard=65024 newer=0 exact=1",
        f"publication_case mode={mode} stale=1 active=0 guard=65024 newer=1 exact=1",
    ]
    if len(rows) != 3 or rows[1:] != cases:
        raise ValueError("missing, extra or reordered publication receipts")
    m = re.fullmatch(r"publication_adapter actual_high=(-?\d+) actual_low=(\d+) warp_high=(-?\d+) warp_low=(\d+) software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-texback-publication-") as tmp:
        target = Path(tmp) / "runtime"
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900, env=clean_env())
        if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
            raise ValueError("upstream identity")
        before = inventory(target)
        for path, (raw, prepared) in SOURCES.items():
            if blob(git(target, "show", f"HEAD:{path}")) != raw or blob(lf((target/path).read_bytes())) != prepared:
                raise ValueError("raw/prepared identity: " + path)
            print(f"source={path} raw={raw} prepared={prepared}", flush=True)
        for path, expected in MANIFESTS.items():
            if blob(git(target, "show", f"HEAD:{path}")) != expected:
                raise ValueError("raw manifest identity: " + path)
        dest = target / DEST
        original = dest.read_bytes()
        prepared = lf(original)
        fixture = lf((ROOT / PROBE).read_bytes())
        if len(prepared) != 10882 or len(fixture) != 9401 or b"mod ai2_publication_baseline" in prepared:
            raise ValueError("unexpected append inputs")
        proposed = prepared + b"\n" + fixture
        if len(proposed) != 20284 or blob(proposed) != POST or proposed[:-len(fixture)-1] != prepared:
            raise ValueError("append postimage or inverse")
        if inventory(target) != before or dest.read_bytes() != original:
            raise ValueError("checkout changed before write")
        dest.write_bytes(proposed)
        after = inventory(target)
        if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != {DEST}:
            raise ValueError("unexpected full checkout delta")
        if dest.read_bytes() != proposed:
            raise ValueError("actual postimage identity")
        print(f"inventory_entries={len(before)} changed=1 upstream={UPSTREAM} post={POST}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for release in (False, True):
            exe = build(target, release)
            for mode in ("normal", "none"):
                run_exact(exe, target, release, mode)
    print("Four isolated texture landing receipts only; no record, notification, production failure, gameplay or FPS proof.")

if __name__ == "__main__":
    main()
