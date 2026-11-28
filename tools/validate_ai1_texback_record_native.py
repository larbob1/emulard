# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated texture record native gate; no production registration."""
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

REVIEWED = "b9cbecca24a7a9a53a8bbd21cf83eefc37a186d2"
PINS = {
    "probes/ai2_texback_record_resource.rs": "80250d2d44288ba0d708f39c4ed674aec6bc5d30",
    "probes/ai2_texback_record_baseline.rs": "6b910244e74f3bdb7b2323a192e4298098865ad7",
    "docs/ai2-texback-record-baseline.md": "871deba94c1786bb60ae69f1e541189b03ac8e54",
    "tools/build_runtime.py": BUILDER,
}
SOURCES = {
    "crates/victory-gpu/src/resource.rs": ("1fff3d6a42db6d2eea17de0b7d325ebec5eb6dfc", "215122c8728e95b3748b135f6c760f0690a959d8"),
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
APPENDS = {
    "crates/victory-gpu/src/resource.rs": ("probes/ai2_texback_record_resource.rs", "314c10076c9fa7f07a8fb24f69b4c44f3b758185"),
    "crates/victory-gpu/src/texback.rs": ("probes/ai2_texback_record_baseline.rs", "5194db29dce999153436641037bc601abfdc17be"),
}
NAMES = ("texback::ai2_record_baseline::actual_record_land_r0",
         "texback::ai2_record_baseline::actual_record_refusal_r1")
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


def parse_receipts(stdout, stderr, case):
    if any("record_adapter" in l or "record_case" in l for l in stdout.splitlines()):
        raise ValueError("receipt in stdout")
    rows = [l for l in stderr.splitlines() if "record_adapter" in l or "record_case" in l]
    if len(rows) != 2:
        raise ValueError("missing, extra or displaced receipts")
    signed = r"(0|-?[1-9][0-9]*)"
    unsigned = r"(0|[1-9][0-9]*)"
    m = re.fullmatch("record_adapter actual_high=" + signed + " actual_low=" + unsigned
                     + " warp_high=" + signed + " warp_low=" + unsigned + " software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")
    if case == 0:
        prefix = "record_case id=0 selected=1 recorded=1 submitted=1 fence=1 healthy=1 subresources=4 gpu_bytes=48 active=48 padding=2512 guard=62976 stale=0 cleanup=1 exact=1"
        m = re.fullmatch(prefix + " extent=" + unsigned + " width=" + unsigned, rows[1])
        if not m:
            raise ValueError("malformed R0 receipt")
        extent, width = map(int, m.groups())
        if not 0 < extent <= 65536 or not extent <= width < 2**64:
            raise ValueError("readback extent/width")
    elif rows[1] != "record_case id=1 selected=1 recorded=0 submitted=0 fence=0 healthy=1 subresources=0 gpu_bytes=0 active=0 padding=2512 guard=62976 stale=1 cleanup=1 exact=1 newer=2560":
        raise ValueError("malformed R1 receipt")

def run_exact(exe, target, release, case):
    profile = "release" if release else "debug"
    name = NAMES[case]
    env = clean_env()
    flags = {"VICTORY_D3D12_WARP": "1", "VICTORY_SWEEP": "0", "VICTORY_TEXTURE_BACK": "7x3f61"}
    env.update(flags)
    print(f"profile={profile} case=R{case} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(flags, sort_keys=True) + " VICTORY_COPY_MODE=absent", flush=True)
    p = direct([str(exe), "--list", "--ignored"], target, env)
    if p.returncode or any(p.stdout.splitlines().count(n + ": test") != 1 for n in NAMES):
        raise ValueError("exact ignored listing")
    p = direct([str(exe), name, "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"], target, env)
    tests = [l for l in p.stdout.splitlines() if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in p.stdout.splitlines() if l.startswith("test result:")]
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if p.returncode or tests != [f"test {name} ... ok"] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        raise ValueError("missing exact native test receipt")
    parse_receipts(p.stdout, p.stderr, case)

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-texback-record-") as tmp:
        owned = Path(tmp).absolute()
        if owned.is_symlink() or owned.is_junction() or not owned.is_dir():
            raise ValueError("unexpected temporary root type")
        canonical = owned.resolve(strict=True)
        if not owned.samefile(canonical) or canonical == ROOT or ROOT in canonical.parents or canonical in ROOT.parents:
            raise ValueError("temporary root identity or overlap")
        target = canonical / "runtime"
        if target.exists() or target.is_symlink() or target.is_junction():
            raise ValueError("runtime child must be absent")
        subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                        "--paired-wave-refresh"], check=True, timeout=900, env=clean_env())
        if (target.is_symlink() or target.is_junction() or not target.is_dir()
                or target.resolve(strict=True) != target or not owned.samefile(canonical)
                or not target.parent.samefile(canonical)):
            raise ValueError("runtime child identity")
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
        writes = {}
        for path, (probe, post) in APPENDS.items():
            dest = target / path
            original = dest.read_bytes()
            prepared = lf(original)
            fixture = lf((ROOT / probe).read_bytes())
            proposed = prepared + b"\n" + fixture
            if not fixture or blob(proposed) != post or proposed[:-len(fixture)-1] != prepared:
                raise ValueError("append postimage or inverse: " + path)
            writes[path] = (original, proposed)
            print(f"append={path} prepared_bytes={len(prepared)} fixture_bytes={len(fixture)} post={post}", flush=True)
        if inventory(target) != before:
            raise ValueError("checkout changed before write")
        for path, (original, proposed) in writes.items():
            dest = target / path
            if dest.resolve(strict=True) != dest or dest.read_bytes() != original:
                raise ValueError("source changed before write")
            dest.write_bytes(proposed)
        after = inventory(target)
        if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != set(APPENDS):
            raise ValueError("unexpected full checkout delta")
        for path, (_, proposed) in writes.items():
            if (target/path).read_bytes() != proposed:
                raise ValueError("actual postimage identity")
        print(f"inventory_entries={len(before)} changed=2 upstream={UPSTREAM}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for release in (False, True):
            exe = build(target, release)
            for case in (0, 1):
                run_exact(exe, target, release, case)
    print("Four isolated texture record/landing receipts only; no ordinary required refusal, notification, production policy, gameplay or FPS proof.")

if __name__ == "__main__":
    main()
