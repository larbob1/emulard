# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply pinned common R2 repair to isolated matched source arms; no build or launch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BUILDER = "31bc201ad006b304542e8b03405c1a9090d76804"
HELPER_HEAD = "5c961054125590ab0ece0484154602a235f0f81c"
HELPER_PATH = "tools/validate_ai1_production_only.py"
HELPER_BLOB = "a9a769feb8a63b662f9a5c515ea1241f39065124"
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
HOST = "crates/victory-gpu/src/host.rs"
TEXBACK = "crates/victory-gpu/src/texback.rs"
R2_PATCH = "patches/paired-wave-texback-selection-r2.patch"
R2_BLOB = "57431b71dc138f7f82c82ea97dd60977530ffeda"
R2_BEFORE = {HOST: "88acbb3b2cf550cdf2303685fcc32249f9e46328",
             TEXBACK: "3102a4f9ed2f80c86a28fcc5070b855143279574"}
R2_AFTER = {HOST: "031a65c12bbab967759383b2a75a3be46c46bbde",
            TEXBACK: "a17dfb5f693163d64ab8f4a60ede71e52c2f596a"}
SHADOW = "crates/victory-gpu/src/shadow.rs"
TEXTURE = "crates/victory-gpu/src/texture.rs"
FORMATS = "crates/victory-formats/src/texture.rs"
EXPECTED = {
    HOST: "88acbb3b2cf550cdf2303685fcc32249f9e46328",
    TEXTURE: "fe0526831acf2b0f68caa4163fda83b251c22bb0",
}
ROUTES = {
    HOST: ("timing", "late_stage", "relay"),
    SHADOW: ("cards", "relay", "wide_back"),
    TEXTURE: ("staging_pool",),
}

def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd)

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def digest(inventory):
    raw = json.dumps(inventory, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()

def helper(checkout):
    if git(checkout, "rev-parse", "HEAD").decode().strip() != HELPER_HEAD:
        raise ValueError("helper checkout identity")
    raw = git(checkout, "show", "HEAD:" + HELPER_PATH)
    if blob(raw) != HELPER_BLOB:
        raise ValueError("helper blob identity")
    scope = {"__name__": "pinned_ai1_rehearsal", "__file__": str(checkout / HELPER_PATH)}
    exec(compile(raw, HELPER_PATH, "exec"), scope)
    return scope

def route_blocks(target, lf):
    out = {}
    for path, names in ROUTES.items():
        source = lf((target / path).read_bytes()).decode()
        for name in names:
            # These pinned module-level definitions end at column-zero }.
            # Fail closed on missing or repeated anchors; do not guess.
            pattern = rf"^(?:pub(?:\(crate\))? )?fn {name}\(\)[^\n]*\{{\n.*?^\}}"
            matches = re.findall(pattern, source, re.M | re.S)
            if len(matches) != 1:
                raise ValueError(f"route anchor {path}:{name}")
            out[f"{path}:{name}"] = matches[0]
    return out

def common_repair(target, scope, pristine):
    lf = scope["lf"]
    inventory = scope["source_inventory"]
    patch = git(ROOT, "show", "HEAD:" + R2_PATCH)
    if blob(patch) != R2_BLOB or lf((ROOT / R2_PATCH).read_bytes()) != patch:
        raise ValueError("R2 patch identity")
    routes = route_blocks(target, lf)
    for name, expected in R2_BEFORE.items():
        path = target / name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(target):
            raise ValueError("unsafe common source path")
        if blob(lf(path.read_bytes())) != expected:
            raise ValueError("R2 preimage mismatch: " + name)
    for args in (("apply", "--check", "-"), ("apply", "-"), ("apply", "--reverse", "--check", "-")):
        subprocess.run(["git", *args], cwd=target, input=patch, check=True, timeout=60)
    for name, expected in R2_AFTER.items():
        if blob(lf((target / name).read_bytes())) != expected:
            raise ValueError("R2 postimage mismatch: " + name)
    common = inventory(target)
    if pristine.keys() != common.keys() or {n for n in pristine if pristine[n] != common[n]} != set(R2_AFTER):
        raise ValueError("unexpected common repair changes")
    if routes != route_blocks(target, lf):
        raise ValueError("common repair altered route predicates")
    print(json.dumps({"common_r2": R2_AFTER, "pristine_inventory_sha256": digest(pristine),
                      "common_inventory_sha256": digest(common)}, sort_keys=True), flush=True)
    return common


def prepare(target, scope, calculate, combined):
    subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"),
                    str(target), "--paired-wave-refresh"], check=True, timeout=900)
    target = target.resolve(strict=True)
    if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
        raise ValueError("runtime revision mismatch")
    inventory = scope["source_inventory"]
    lf = scope["lf"]
    pristine = inventory(target)
    originals = {name: (target / name).read_bytes() for name in scope["BEFORE"]}
    for name, expected in {**EXPECTED, **scope["BEFORE"]}.items():
        if blob(lf((target / name).read_bytes())) != expected:
            raise ValueError("prepared identity mismatch: " + name)
    before = common_repair(target, scope, pristine)
    result, receipt = calculate(originals, combined, combined, combined)
    expected = scope["AFTER"] if combined else scope["BEFORE"]
    if set(result) != set(expected) or any(blob(result[n]) != h for n, h in expected.items()):
        raise ValueError("selected postimage mismatch")
    wanted = set(expected) if combined else set()
    if set(receipt["would_change"]) != wanted:
        raise ValueError("unexpected selected changes")
    for name in sorted(wanted):
        path = target / name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(target):
            raise ValueError("unsafe source path")
        data = result[name]
        path.write_bytes(data.replace(b"\n", b"\r\n") if b"\r\n" in originals[name] else data)
    after = inventory(target)
    if before.keys() != after.keys() or {n for n in before if before[n] != after[n]} != wanted:
        raise ValueError("unexpected per-arm changes")
    for name, h in expected.items():
        if blob(lf((target / name).read_bytes())) != h:
            raise ValueError("materialized source mismatch")
    subprocess.run(["git", "diff", "--check"], cwd=target, check=True)
    return pristine, before, after, route_blocks(target, lf)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--helper", type=Path, required=True)
    p.add_argument("--preview", type=Path, required=True)
    a = p.parse_args()
    if os.name != "nt":
        raise SystemExit("Windows source preparation parity with #96 required")
    if blob(git(ROOT, "show", "HEAD:tools/build_runtime.py")) != BUILDER:
        raise ValueError("builder identity")
    scope = helper(a.helper.resolve(strict=True))
    calculate = scope["load_preview"](a.preview.resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="ai1-matched-route-") as tmp:
        pristine0, before0, control, routes0 = prepare(Path(tmp) / "control", scope, calculate, False)
        pristine1, before1, candidate, routes1 = prepare(Path(tmp) / "candidate", scope, calculate, True)
        if pristine0 != pristine1 or before0 != before1:
            raise ValueError("independent baseline inventory differs")
        if control.keys() != candidate.keys():
            raise ValueError("cross-arm path inventory differs")
        changed = {n for n in control if control[n] != candidate[n]}
        if changed != {SHADOW, FORMATS}:
            raise ValueError(f"cross-arm changed paths: {sorted(changed)}")
        if routes0 != routes1:
            raise ValueError("selected route predicates changed")
        common0 = {n:v for n,v in control.items() if n not in changed}
        common1 = {n:v for n,v in candidate.items() if n not in changed}
        if common0 != common1:
            raise ValueError("nonselected source differs")
        print(f"upstream={UPSTREAM} entries={len(control)} changed={sorted(changed)}", flush=True)
        print(f"control_inventory_sha256={digest(control)} candidate_inventory_sha256={digest(candidate)}", flush=True)
        print(f"nonselected_entries={len(common0)} nonselected_inventory_sha256={digest(common0)}", flush=True)
        for label, source in sorted(routes0.items()):
            print(json.dumps({"route":label, "blob_lf":blob(source.encode()), "source":source},
                             sort_keys=True), flush=True)
    print("Common R2 source-only parity and route predicate receipt; no evaluated environment, binary, gameplay or launch evidence.")

if __name__ == "__main__":
    main()
