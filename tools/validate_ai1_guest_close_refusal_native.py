# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated texture guest-close refusal native gate; no production registration."""
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

REVIEWED = "af2478aa42c665db38789778a12142c51dbb67ac"
PINS = {
    "probes/ai2_texback_guest_close_list.rs": "63026acc8e8d372295e30735ef7cd8c40864020c",
    "probes/ai2_texback_guest_close_observe.rs": "01955b95b819a6dda86a57615a100adb717187b9",
    "probes/ai2_texback_guest_close_host.rs": "c35f90e5d9f8ec6daa813d9db0999a081b3dae68",
    "probes/ai2_texback_record_resource.rs": "80250d2d44288ba0d708f39c4ed674aec6bc5d30",
    "tools/prepare_ai2_guest_close_refusal.py": "de898fecd75c82604d75a25aaf15685830c37957",
    "docs/ai2-texback-guest-close-refusal.md": "f1e55b3e5d193d86cc88473f96197a48bebcc069",
    "tools/build_runtime.py": BUILDER,
}
SOURCES = {
    "crates/victory-gpu/src/list.rs": ("3bf89f3c9b17f14c2ec4fa4480e3378e6ac8857e",)*2,
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
    "Cargo.lock": "29bab8c72233fbd9552e646c79316bc9439df0d7",
}
APPENDS = {
    "crates/victory-gpu/src/host.rs": ("probes/ai2_texback_guest_close_host.rs", "c254622dd955adaac0d2191faf35c9f7c1404d23"),
    "crates/victory-gpu/src/texback.rs": ("probes/ai2_texback_guest_close_observe.rs", "daa97476498b80432032f5cb2965e0531aecd304"),
    "crates/victory-gpu/src/resource.rs": ("probes/ai2_texback_record_resource.rs", "314c10076c9fa7f07a8fb24f69b4c44f3b758185"),
    "crates/victory-gpu/src/list.rs": ("probes/ai2_texback_guest_close_list.rs", "791ef1c84af00f536821d07a4b3f3bed1633b58f"),
}
LENGTHS = dict(zip(APPENDS, (453335, 14667, 161182, 89429)))
NAMES = ("host::ai2_guest_close_refusal::actual_guest_close_control",
         "host::ai2_guest_close_refusal::actual_guest_close_refusal")


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
    if case not in range(len(NAMES)):
        raise ValueError("unsupported guest close case")
    if any("guest_close_adapter" in l or "guest_close_case" in l for l in stdout.splitlines()):
        raise ValueError("receipt in stdout")
    rows = [l for l in stderr.splitlines() if "guest_close_adapter" in l or "guest_close_case" in l]
    if len(rows) != 2:
        raise ValueError("missing, extra or displaced receipts")
    signed = r"(0|-?[1-9][0-9]*)"
    unsigned = r"(0|[1-9][0-9]*)"
    m = re.fullmatch("guest_close_adapter actual_high=" + signed + " actual_low=" + unsigned
                     + " warp_high=" + signed + " warp_low=" + unsigned + " software=1", rows[0])
    if not m:
        raise ValueError("malformed adapter receipt")
    ah, al, wh, wl = map(int, m.groups())
    if (ah, al) != (wh, wl) or not -2**31 <= ah < 2**31 or not 0 <= al < 2**32:
        raise ValueError("adapter LUID mismatch")
    expected = (
        f"guest_close_case refused={case} selected=1 current=1 consumed=1 subresources=4 "
        + r"extent=([1-9][0-9]*) width=(unavailable|[1-9][0-9]*) "
        + f"wanted_after=0 recorded={1-case} guest_status=0 submitted=0 fence=0 healthy=1 "
          "preserved=2560 guards=62976 cleanup=1"
    )
    m = re.fullmatch(expected, rows[1])
    if not m:
        raise ValueError("malformed guest close receipt")
    extent, width = int(m[1]), m[2]
    if not 0 < extent <= 65536:
        raise ValueError("invalid footprint extent")
    if case == 0:
        if width == "unavailable" or not extent <= int(width) < 2**64:
            raise ValueError("invalid recorded width")
    elif width != "unavailable":
        raise ValueError("adverse width must be unavailable")

UINT = r'(?:0|[1-9][0-9]*)'

def parse_listing(stdout, stderr, code):
    if code != 0:
        raise ValueError('listing exit')
    rows = [line for line in stdout.splitlines() if line.strip()]
    if not rows:
        raise ValueError('missing listing')
    footer = re.fullmatch(r'(' + UINT + r') tests?, 0 benchmarks?', rows[-1])
    if not footer:
        raise ValueError('listing footer')
    names = []
    for line in rows[:-1]:
        entry = re.fullmatch(r'(\S+): test', line)
        if not entry:
            raise ValueError('invalid listing row')
        names.append(entry.group(1))
    if len(names) != int(footer.group(1)) or len(names) != len(set(names)):
        raise ValueError('listing cardinality')
    if any(re.search(r'\b\S+: (?:test|benchmark)\b|\b\d+ tests?, \d+ benchmarks?\b|\bpanicked at\b', line) for line in stderr.splitlines()):
        raise ValueError('contradictory listing stderr')
    return set(names)

def verify_discovery(full, ignored):
    namespace = "host::ai2_guest_close_refusal::"
    if ({n for n in full if n.startswith(namespace)} != set(NAMES)
            or {n for n in ignored if n.startswith(namespace)} != set(NAMES)
            or not ignored <= full):
        raise ValueError('discovery mismatch')
    return len(full) - 1

def verify_framing(stdout, stderr, code, name, filtered):
    if code != 0 or filtered < 0:
        raise ValueError('exit or filtered count')
    out, err = stdout.splitlines(), stderr.splitlines()
    if any(re.search(r'\bpanicked at\b|\bthread .* panicked\b', l, re.IGNORECASE) for l in out+err):
        raise ValueError('unexpected panic')
    framing = re.compile(r'\btest\s+\S+\s+\.\.\.|^\s*test\s|\brunning\s+\d+\s+tests?\b|test result:')
    if any(framing.search(l) for l in err):
        raise ValueError('contradictory stderr')
    rows = [l for l in out if framing.search(l)]
    summary = (r'test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; '
               + str(filtered) + r' filtered out; finished in [0-9]+(?:\.[0-9]+)?s')
    if len(rows) != 3 or rows[:2] != ['running 1 test', f'test {name} ... ok'] or not re.fullmatch(summary, rows[2]):
        raise ValueError('exact ordered framing')


def run_exact(exe, target, release, case, prior_discovery):
    profile = "release" if release else "debug"
    name = NAMES[case]
    env = clean_env()
    flags = {"VICTORY_D3D12_WARP": "1", "VICTORY_SWEEP": "0", "VICTORY_TEXTURE_BACK": "7x3f61"}
    env.update(flags)
    print(f"profile={profile} case={case} executable_sha256={hashlib.sha256(exe.read_bytes()).hexdigest()}", flush=True)
    print("fixture env=" + json.dumps(flags, sort_keys=True) + " VICTORY_COPY_MODE=absent VICTORY_GPU_TIMING=absent", flush=True)
    p = direct([str(exe), "--list"], target, env)
    full = parse_listing(p.stdout, p.stderr, p.returncode)
    p = direct([str(exe), "--list", "--ignored"], target, env)
    ignored = parse_listing(p.stdout, p.stderr, p.returncode)
    filtered = verify_discovery(full, ignored)
    if prior_discovery is not None and prior_discovery != (full, ignored):
        raise ValueError("profile discovery changed")
    print(f"discovery full={len(full)} ignored={len(ignored)} filtered={filtered}", flush=True)
    p = direct([str(exe), name, "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"], target, env)
    print(f"child_exit case={case} code={p.returncode}", flush=True)
    verify_framing(p.stdout, p.stderr, p.returncode, name, filtered)
    parse_receipts(p.stdout, p.stderr, case)
    print(f"accepted case={case} observation={'refusal' if case else 'control'}", flush=True)
    return full, ignored

def main():
    if os.name != "nt":
        raise SystemExit("Windows native execution required")
    for path, expected in PINS.items():
        if blob(git(ROOT, "show", f"{REVIEWED}:{path}")) != expected or blob(git(ROOT, "show", f"HEAD:{path}")) != expected or blob(lf((ROOT/path).read_bytes())) != expected:
            raise ValueError("reviewed input identity: " + path)
    with tempfile.TemporaryDirectory(prefix="ai1-guest-close-refusal-") as tmp:
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
            if blob(git(target, "show", f"HEAD:{path}")) != expected or blob(lf((target/path).read_bytes())) != expected:
                raise ValueError("raw/prepared manifest identity: " + path)
            print(f"manifest={path} raw={expected} prepared={expected}", flush=True)
        cmd = [sys.executable, str(ROOT / "tools/prepare_ai2_guest_close_refusal.py"), str(target)]
        expected_repaired = {path: SOURCES[path][1] for path in APPENDS}
        expected_repaired["crates/victory-gpu/src/texback.rs"] = "a0eba6f9d4b81fcab3f50691657e72421fbe5c4a"
        for apply in (False, True):
            p = subprocess.run(cmd + (["--apply"] if apply else []), cwd=ROOT,
                               capture_output=True, text=True, errors="replace",
                               check=True, timeout=120, env=clean_env())
            print(p.stdout, flush=True)
            print(p.stderr, flush=True)
            rows = [l for l in p.stdout.splitlines() if l.startswith("post=")]
            for path, (_, post) in APPENDS.items():
                pattern = re.escape(f"post={path} repaired={expected_repaired[path]} postimage={post} bytes={LENGTHS[path]}")
                if sum(bool(re.fullmatch(pattern, l)) for l in rows) != 1:
                    raise ValueError("missing exact intermediate/postimage receipt: " + path)
            if len(rows) != len(APPENDS):
                raise ValueError("extra postimage receipt")
            if not apply and inventory(target) != before:
                raise ValueError("dry run changed checkout")
        after = inventory(target)
        if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != set(APPENDS):
            raise ValueError("unexpected full checkout delta")
        for path, (_, post) in APPENDS.items():
            data = lf((target/path).read_bytes())
            if blob(data) != post or len(data) != LENGTHS[path]:
                raise ValueError("actual postimage identity: " + path)
        print(f"inventory_entries={len(before)} changed=4 upstream={UPSTREAM}", flush=True)
        subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
        for release in (False, True):
            exe = build(target, release)
            digest = hashlib.sha256(exe.read_bytes()).hexdigest()
            prior_discovery = None
            for case in range(len(NAMES)):
                if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
                    raise ValueError("profile executable changed before case")
                prior_discovery = run_exact(exe, target, release, case, prior_discovery)
                if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
                    raise ValueError("profile executable changed after case")
    print("Two control and two controlled pre-allocation refusal observations; no actual OOM, submission, publication, production inclusion, gameplay or FPS proof.")

if __name__ == "__main__":
    main()
