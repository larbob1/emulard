# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only preview. Never writes prepared runtime source."""
import argparse
import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITS = (
    ("shadow.rs", "                let Some((first, n)) = back_piece(host, old, &mut title, &mut mask, &mut runs, read) else {", "                #[cfg(feature = \"diagnostics\")]\n                dirty_observation::sample(0, host, old);\n                let Some((first, n)) = back_piece(host, old, &mut title, &mut mask, &mut runs, read) else {"),
    ("shadow.rs", "        let Some(first) = first_difference(gpu, old) else {", "        #[cfg(feature = \"diagnostics\")]\n        dirty_observation::sample(1, gpu, old);\n        let Some(first) = first_difference(gpu, old) else {"),
    ("shadow.rs", "        let Some(first) = first_difference(gpu, held) else {", "        #[cfg(feature = \"diagnostics\")]\n        dirty_observation::sample(2, gpu, held);\n        let Some(first) = first_difference(gpu, held) else {"),
    ("copystat.rs", "pub(crate) fn log(frames: f64) {\n    let counted = COUNT[C::Frames as usize].swap(0, Relaxed);", "pub(crate) fn log(frames: f64) {\n    if let Some(rows) = crate::shadow::dirty_observation_snapshot() {\n        for (path, [samples, bytes, chunks, unequal]) in rows.into_iter().enumerate() {\n            tracing::info!(\"dirty_observe_v1 path={} samples={} bytes={} chunks={} unequal={}\", path, samples, bytes, chunks, unequal);\n        }\n    }\n    let counted = COUNT[C::Frames as usize].swap(0, Relaxed);"),
)


def preview(sources, bridge):
    result = dict(sources)
    if "mod dirty_observation {" in result["shadow.rs"]:
        raise ValueError("observation module already present")
    for path, old, new in EDITS:
        if result[path].count(old) != 1:
            raise ValueError("missing or ambiguous review anchor: " + path)
        result[path] = result[path].replace(old, new, 1)
    result["shadow.rs"] += "\n" + bridge
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    src = args.prepared / "crates/victory-gpu/src"
    sources = {name: (src / name).read_text(encoding="utf-8") for name in ("shadow.rs", "copystat.rs")}
    result = preview(sources, (ROOT / "probes/dirty_observation_bridge.rs").read_text(encoding="utf-8"))
    for name in sources:
        print("".join(difflib.unified_diff(sources[name].splitlines(True), result[name].splitlines(True),
                                          "a/" + name, "b/" + name)), end="")


if __name__ == "__main__":
    main()
