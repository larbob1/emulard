# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only preview. Never writes prepared runtime source."""
import argparse
import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITS = (
    ("crates/victory-gpu/src/shadow.rs", "                let Some((first, n)) = back_piece(host, old, &mut title, &mut mask, &mut runs, read) else {", "                #[cfg(feature = \"diagnostics\")]\n                dirty_observation::sample(0, host, old);\n                let Some((first, n)) = back_piece(host, old, &mut title, &mut mask, &mut runs, read) else {"),
    ("crates/victory-gpu/src/shadow.rs", "        let Some(first) = first_difference(gpu, old) else {", "        #[cfg(feature = \"diagnostics\")]\n        dirty_observation::sample(1, gpu, old);\n        let Some(first) = first_difference(gpu, old) else {"),
    ("crates/victory-gpu/src/shadow.rs", "        let Some(first) = first_difference(gpu, held) else {", "        #[cfg(feature = \"diagnostics\")]\n        dirty_observation::sample(2, gpu, held);\n        let Some(first) = first_difference(gpu, held) else {"),
    ("crates/victory-gpu/src/copystat.rs", "pub(crate) fn log(frames: f64) {\n    let counted = COUNT[C::Frames as usize].swap(0, Relaxed);", "pub(crate) fn log(frames: f64) {\n    if let Some(rows) = crate::shadow::dirty_observation_snapshot() {\n        for (path, [samples, bytes, chunks, unequal]) in rows.into_iter().enumerate() {\n            tracing::info!(\"dirty_observe_v1 path={} samples={} bytes={} chunks={} unequal={}\", path, samples, bytes, chunks, unequal);\n        }\n    }\n    let counted = COUNT[C::Frames as usize].swap(0, Relaxed);"),
    ("crates/victory-gpu/src/lib.rs", "#[cfg(windows)]\npub use host::on_failure;", "#[cfg(windows)]\npub use host::on_failure;\n#[cfg(all(windows, feature = \"diagnostics\"))]\npub use shadow::init_dirty_observation;"),
    ("crates/victory-hle/src/lib.rs", "pub use victory_gpu::console;", "pub use victory_gpu::console;\n#[cfg(all(windows, feature = \"diagnostics\"))]\npub use victory_gpu::init_dirty_observation;"),
    ("apps/victory/src/run.rs", "    // A title that relaunched itself: the old process must be gone first.", "    // Read the diagnostic option once before title setup or GPU work.\n    #[cfg(feature = \"diagnostics\")]\n    let _ = victory_hle::init_dirty_observation(\n        std::env::var_os(\"VICTORY_DIRTY_OBSERVE\").is_some_and(|v| v == \"1\"),\n    );\n    // A title that relaunched itself: the old process must be gone first."),
)


def preview(sources, bridge):
    result = dict(sources)
    if "mod dirty_observation {" in result["crates/victory-gpu/src/shadow.rs"]:
        raise ValueError("observation module already present")
    for path, old, new in EDITS:
        if result[path].count(old) != 1:
            raise ValueError("missing or ambiguous review anchor: " + path)
        result[path] = result[path].replace(old, new, 1)
    result["crates/victory-gpu/src/shadow.rs"] += "\n" + bridge
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    sources = {name: (args.prepared / name).read_text(encoding="utf-8") for name in dict.fromkeys(path for path, _, _ in EDITS)}
    result = preview(sources, (ROOT / "probes/dirty_observation_bridge.rs").read_text(encoding="utf-8"))
    for name in sources:
        print("".join(difflib.unified_diff(sources[name].splitlines(True), result[name].splitlines(True),
                                          "a/" + name, "b/" + name)), end="")


if __name__ == "__main__":
    main()
