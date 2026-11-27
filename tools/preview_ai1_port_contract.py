# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only source-port preview; not registered by build_runtime.py.

Calculate exact prepared postimages in memory. No source writes, compiler,
installation, or runtime execution. The default is the untouched control.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
SHADOW = "crates/victory-gpu/src/shadow.rs"
TEXTURE = "crates/victory-formats/src/texture.rs"
PREIMAGE = {
    SHADOW: "40f1ae02506de251d51e00ebfd36f58e58e7621b",
    TEXTURE: "fa719c93953d9e6589c4d2cd27a13d773863c316",
}
SHADOW_HASH = {False: PREIMAGE[SHADOW], True: "7229972b47fc789ec2c9968f48b41db6b8e785f0"}
TEXTURE_HASH = {
    (False, False): PREIMAGE[TEXTURE],
    (True, False): "b38ff33b12552b996c614b6819989db5adb9b3c2",
    (False, True): "0debdf9eb188313a25f0541e3ba4ff4972163735",
    (True, True): "9d5f96c702a0a125f04bd34d4247091a3e23c131",
}
CUT = ("            (at - (start + at) % PIECE).max(from)",
       "            at.saturating_sub((start + at) % PIECE).max(from)")
# Literal blocks from exact #64 and #65 reviewed previews. The latter
# retains the original spread function name for actual Layout::new callers.
DETILE = ("        let mut runs = Vec::new();\n        if !linear {\n            let mut first_linear = 0;\n            let mut first_tiled = self.column(m, 0) as usize;\n            for x in 1..m.width {\n                let offset = self.column(m, x) as usize;\n                let at = x as usize * n;\n                if offset != first_tiled + (at - first_linear) {\n                    runs.push((first_tiled, first_linear, at - first_linear));\n                    first_tiled = offset;\n                    first_linear = at;\n                }\n            }\n            runs.push((first_tiled, first_linear, bytes - first_linear));\n        }\n        // A mip can end partway through the last run. Check the other runs\n        // once so each row can copy them as fixed-size chunks.\n        let (body, last) = runs.split_at(runs.len().saturating_sub(1));\n        let chunk_size = body.first().map(|run| run.2).filter(|&size| {\n            body.iter()\n                .all(|&(offset, _, len)| len == size && offset.is_multiple_of(size))\n        });\n",
          "        let mut runs = Vec::new();\n        let mut last = None;\n        if !linear {\n            let mut first_linear = 0;\n            let mut first_tiled = self.column(m, 0) as usize;\n            for x in 1..m.width {\n                let offset = self.column(m, x) as usize;\n                let at = x as usize * n;\n                if offset != first_tiled + (at - first_linear) {\n                    runs.push((first_tiled, first_linear, at - first_linear));\n                    first_tiled = offset;\n                    first_linear = at;\n                }\n            }\n            last = Some((first_tiled, first_linear, bytes - first_linear));\n        }\n        // A mip can end partway through the last run. Check the other runs\n        // once so each row can copy them as fixed-size chunks.\n        let body = runs.as_slice();\n        let last = last.as_slice();\n        let chunk_size = body.first().map(|run| run.2).filter(|&size| {\n            body.iter()\n                .all(|&(offset, _, len)| len == size && offset.is_multiple_of(size))\n        });\n")
SPREAD = ("fn spread(bits: &[u32]) -> Vec<u32> {\n    (0..1u32 << bits.len())\n        .map(|c| {\n            bits.iter()\n                .enumerate()\n                .map(|(i, &to)| ((c >> i) & 1) << to)\n                .sum()\n        })\n        .collect()\n}",
          "fn spread(bits: &[u32]) -> Vec<u32> {\n    // The caller supplies distinct address-bit positions within a block.\n    // Extend the previous prefix in increasing coordinate order.\n    let count = 1u32 << bits.len();\n    let mut offsets = Vec::with_capacity(count as usize);\n    offsets.push(0u32);\n    for &to in bits {\n        let increment = 1u32 << to;\n        let half = offsets.len();\n        for i in 0..half {\n            let next = offsets[i] + increment;\n            offsets.push(next);\n        }\n    }\n    offsets\n}")


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def normalize(data):
    if b"\r\n" in data and b"\n" in data.replace(b"\r\n", b""):
        raise ValueError("mixed line endings")
    result = data.replace(b"\r\n", b"\n")
    if b"\r" in result:
        raise ValueError("unexpected carriage return")
    return result


def replace_once(source, pair):
    old, new = pair
    if source.count(old) != 1 or new in source:
        raise ValueError("absent, repeated or already applied anchor")
    return source.replace(old, new, 1)


def calculate(sources, c=False, d=False, s=False):
    """Return selected canonical bytes and receipt; never mutate inputs."""
    if any(type(mode) is not bool for mode in (c, d, s)):
        raise ValueError("selection bits must be boolean")
    if set(sources) != set(PREIMAGE):
        raise ValueError("unexpected source inventory")
    prepared = {path: normalize(data) for path, data in sources.items()}
    for path, data in prepared.items():
        if blob(data) != PREIMAGE[path]:
            raise ValueError("prepared preimage mismatch: " + path)
    result = dict(prepared)
    if c:
        result[SHADOW] = replace_once(prepared[SHADOW].decode(), CUT).encode()
    texture = prepared[TEXTURE].decode()
    if d:
        texture = replace_once(texture, DETILE)
    if s:
        texture = replace_once(texture, SPREAD)
    result[TEXTURE] = texture.encode()
    if d and s:
        reverse = replace_once(replace_once(prepared[TEXTURE].decode(), SPREAD), DETILE)
        if reverse.encode() != result[TEXTURE]:
            raise ValueError("texture replacement order mismatch")
    expected = {SHADOW: SHADOW_HASH[c], TEXTURE: TEXTURE_HASH[d, s]}
    actual = {path: blob(data) for path, data in result.items()}
    if actual != expected:
        raise ValueError("selected postimage mismatch")
    return result, {
        "upstream": UPSTREAM, "mode": {"C": c, "D": d, "S": s},
        "preimage_lf": dict(PREIMAGE), "postimage_lf": actual,
        "would_change": sorted(path for path in result if result[path] != prepared[path]),
        "scope": "read-only source preview; no registration, build or native receipt",
    }


def git_head(checkout):
    root = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "--show-toplevel"], text=True).strip()
    if Path(root).resolve() != checkout:
        raise ValueError("checkout must be the repository root")
    return subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()


def preview(checkout, c=False, d=False, s=False):
    checkout = checkout.resolve(strict=True)
    if git_head(checkout) != UPSTREAM:
        raise ValueError("unsupported upstream revision")
    sources = {}
    for name in PREIMAGE:
        path = checkout / name
        if not path.resolve(strict=True).is_relative_to(checkout) or not path.is_file():
            raise ValueError("source outside checkout")
        sources[name] = path.read_bytes()
    _, receipt = calculate(sources, c, d, s)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkout", type=Path)
    p.add_argument("--correct-cut", action="store_true")
    p.add_argument("--detile-last-run", action="store_true")
    p.add_argument("--spread-table", action="store_true")
    a = p.parse_args()
    try:
        result = preview(a.checkout, a.correct_cut, a.detile_last_run, a.spread_table)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        p.exit(1, f"Preview refused: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
