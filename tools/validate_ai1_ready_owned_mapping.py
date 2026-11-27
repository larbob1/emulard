# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual ready recording parity with bounded owned OS pages and shadow registry.

No arbitrary memory access, GPU submission, title or install.
Only the fixture-owned pages can enter the actual committed/lookup path.
"""
import argparse
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
PINS = {
    "memory.rs": ("c25636783511fdfbf9692fdd36ef150f69ea666e", "c25636783511fdfbf9692fdd36ef150f69ea666e"),
    "host.rs": ("458d146aedf6f13dac80782d283a048d80e4a931", "88acbb3b2cf550cdf2303685fcc32249f9e46328"),
    "shadow.rs": ("4fa43df7932bb6692d164384cd28b1f08f3001ee", "40f1ae02506de251d51e00ebfd36f58e58e7621b"),
}
TEST = "memory::ai1_ready_owned_review::actual_ready_owned_mapping_parity"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path)


def pinned(path, head, file, pin):
    if git(path, "rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("checkout mismatch")
    raw = git(path, "show", "HEAD:" + file)
    if blob(raw) != pin:
        raise ValueError("blob mismatch")
    print(f"checkout={head} file={file} blob={pin}", flush=True)
    return raw


def constants(source, names):
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in names:
                if t.id in values:
                    raise ValueError("duplicate anchor")
                values[t.id] = ast.literal_eval(node.value)
    if set(values) != set(names) or not all(isinstance(v, str) for v in values.values()):
        raise ValueError("missing string anchor")
    return values


def normalize(raw):
    if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b""):
        raise ValueError("mixed source line endings")
    data = raw.replace(b"\r\n", b"\n")
    if b"\r" in data:
        raise ValueError("unexpected CR")
    return data


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("source anchor mismatch")
    return source.replace(old, new, 1)


def write(path, text, original):
    data = text.encode()
    path.write_bytes(data.replace(b"\n", b"\r\n") if b"\r\n" in original else data)
    print(f"{path.name} test_postimage_lf={blob(data)}", flush=True)


def prepare(target, proposal, prior):
    vals = constants(pinned(proposal, "036dec4dc4b6a012d2e860e1ae779b67f75719eb",
        "tools/preview_ai0_ready_copy_prefix.py", "bf5e1bbfe35de159756cd0dfdc32c65fcef5c68e"),
        ("START", "OLD", "NEW"))
    helpers = constants(pinned(prior, "344e09c49f406d8a986eb8ff25eef2189bdabc19",
        "tools/validate_ai1_ready_prefix.py", "e3d9e129e4f51d55deea7be705833d1445025f31"),
        ("HOST_HELPER", "SHADOW_HELPER"))
    subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                    "--paired-wave-refresh"], check=True)
    if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
        raise ValueError("upstream mismatch")
    src = target / "crates/victory-gpu/src"
    originals, prepared = {}, {}
    for file, (raw_pin, prepared_pin) in PINS.items():
        raw = git(target, "show", "HEAD:crates/victory-gpu/src/" + file)
        originals[file] = (src / file).read_bytes()
        p = normalize(originals[file])
        if blob(raw) != raw_pin or blob(p) != prepared_pin:
            raise ValueError("source identity mismatch: " + file)
        prepared[file] = p.decode()
        print(f"{file} raw={raw_pin} prepared_lf={prepared_pin}", flush=True)
    text = prepared["memory.rs"]
    start, old, new = (vals[k] for k in ("START", "OLD", "NEW"))
    if text.count(start) != 1 or text.count(old) != 1 or "ready_skip_prefix" in text:
        raise ValueError("ready anchors mismatch")
    method = text[text.index(start):]
    if not method.endswith("}\n"):
        raise ValueError("ready boundary mismatch")
    clone = replace_once(method, start, "fn ready_skip_prefix(\n")
    clone = replace_once(clone, old, new)
    # Keep actual committed and shadow::find; restrict the query to pages
    # owned by this exact fixture. No unowned address is passed to Windows.
    text = replace_once(text,
        "        if !crate::texture::committed(start as *const u8, PAGE as usize) {",
        """        #[cfg(all(test, feature = "diagnostics"))]
        if !ai1_ready_owned_review::owns(start, PAGE) {
            self.refused.insert(page);
            return;
        }
        if !crate::texture::committed(start as *const u8, PAGE as usize) {""")
    fixture = (ROOT / "probes/ai1_ready_owned_mapping.rs").read_text(encoding="utf-8")
    if fixture.count("fn actual_ready_owned_mapping_parity(") != 1:
        raise ValueError("fixture marker mismatch")
    write(src / "memory.rs", text + "\n#[cfg(test)]\n" + clone + "\n" + fixture, originals["memory.rs"])
    for name, key in (("host.rs", "HOST_HELPER"), ("shadow.rs", "SHADOW_HELPER")):
        write(src / name, prepared[name] + "\n" + helpers[key], originals[name])
    subprocess.run(["git", "diff", "--check"], cwd=target, check=True)


def run_exact(target, release, query):
    args = ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib", "--features", "diagnostics"]
    if release:
        args.append("--release")
    args.extend([TEST, "--", "--exact", "--test-threads=1"])
    env = dict(os.environ, VICTORY_D3D12_WARP="1", VICTORY_BACK_AVX2="0", VICTORY_BACK_SPARSE_MERGE="0",
               VICTORY_INPLACE="0", VICTORY_CARD_BUFFERS="0", VICTORY_COMMITTED_QUERY=query)
    r = subprocess.run(args, cwd=target, env=env, capture_output=True,
                       text=True, errors="replace", timeout=3600)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    expected = f"test {TEST} ... ok"
    tests = [l for l in lines if re.match(r"^test \S+ \.\.\. ", l)]
    summaries = [l for l in lines if l.startswith("test result:")]
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if r.returncode or tests != [expected] or len(summaries) != 1 or not re.fullmatch(summary, summaries[0]):
        print((r.stderr + "\n" + r.stdout)[-16000:], flush=True)
        raise ValueError("missing exact ready caller receipt")
    print(("release" if release else "debug") + " diagnostics query=" + query + " " + expected, flush=True)
    print(summaries[0], flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proposal", type=Path, required=True)
    p.add_argument("--prior", type=Path, required=True)
    a = p.parse_args()
    if os.name != "nt":
        raise SystemExit("Windows WARP required")
    with tempfile.TemporaryDirectory(prefix="ai1-ready-owned-") as tmp:
        target = Path(tmp) / "runtime"
        prepare(target, a.proposal.resolve(), a.prior.resolve())
        for query in ('0', '1'):
            run_exact(target, False, query)
            run_exact(target, True, query)
    print("Actual ready recording parity with owned OS pages and registry; no submission/gameplay acceptance")


if __name__ == "__main__":
    main()
