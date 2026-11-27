#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Review only: render exact hook diff against supplied source; never write source."""
import argparse
import difflib
from pathlib import Path

REPLACEMENTS = [
    [
        "queue.rs",
        "    execute_now(this, count, lists);\n    #[cfg(windows)]\n    {\n        let us = started.elapsed().as_micros() as u64;",
        "    #[cfg(all(windows, feature = \"diagnostics\"))]\n    let observation = crate::cpu_trace::begin(crate::cpu_trace::Hook::Execute);\n    execute_now(this, count, lists);\n    #[cfg(all(windows, feature = \"diagnostics\"))]\n    crate::cpu_trace::end(observation, true);\n    #[cfg(windows)]\n    {\n        let us = started.elapsed().as_micros() as u64;"
    ],
    [
        "queue.rs",
        "    let hr = present_now(this, planes, plane_parameters);\n    #[cfg(windows)]\n    {\n        crate::framelog::add(crate::framelog::T::PresentUs, presenting.elapsed().as_micros() as u64);",
        "    #[cfg(all(windows, feature = \"diagnostics\"))]\n    let observation = crate::cpu_trace::begin(crate::cpu_trace::Hook::PresentCall);\n    let hr = present_now(this, planes, plane_parameters);\n    #[cfg(all(windows, feature = \"diagnostics\"))]\n    crate::cpu_trace::end(observation, hr >= 0);\n    #[cfg(windows)]\n    {\n        crate::framelog::add(crate::framelog::T::PresentUs, presenting.elapsed().as_micros() as u64);"
    ],
    [
        "frame.rs",
        "        std::thread::sleep(limit);\n        TIMEOUT",
        "        #[cfg(all(windows, feature = \"diagnostics\"))]\n        let observation = crate::cpu_trace::begin(crate::cpu_trace::Hook::PaceSleep);\n        std::thread::sleep(limit);\n        #[cfg(all(windows, feature = \"diagnostics\"))]\n        crate::cpu_trace::end(observation, true);\n        TIMEOUT"
    ],
    [
        "frame.rs",
        "        std::thread::sleep(wait);\n        last(kind).fetch_max(tick, Ordering::Relaxed);",
        "        #[cfg(all(windows, feature = \"diagnostics\"))]\n        let observation = crate::cpu_trace::begin(crate::cpu_trace::Hook::PaceSleep);\n        std::thread::sleep(wait);\n        #[cfg(all(windows, feature = \"diagnostics\"))]\n        crate::cpu_trace::end(observation, true);\n        last(kind).fetch_max(tick, Ordering::Relaxed);"
    ],
    [
        "lib.rs",
        "#[cfg(windows)]\npub mod framelog;",
        "#[cfg(windows)]\npub mod framelog;\n#[cfg(all(windows, feature = \"diagnostics\"))]\nmod cpu_trace;\n#[cfg(all(windows, feature = \"diagnostics\"))]\npub use cpu_trace::initialize as initialize_cpu_trace;"
    ],
[
    "hle_lib.rs",
    "pub use victory_gpu::console;",
    "pub use victory_gpu::console;\n#[cfg(all(windows, feature = \"diagnostics\"))]\npub use victory_gpu::initialize_cpu_trace;"
],
[
    "app_run.rs",
    "    // SAFETY: imports are bound; from here on we run title code.\n    let main = unsafe { Arc::new(image).spawn_main(dlls)? };",
    "    #[cfg(feature = \"diagnostics\")]\n    victory_hle::initialize_cpu_trace(title_dir);\n    // SAFETY: imports are bound; from here on we run title code.\n    let main = unsafe { Arc::new(image).spawn_main(dlls)? };"
]
]

SOURCE_PATHS = {
    "queue.rs": "crates/victory-gpu/src/queue.rs",
    "frame.rs": "crates/victory-gpu/src/frame.rs",
    "lib.rs": "crates/victory-gpu/src/lib.rs",
    "hle_lib.rs": "crates/victory-hle/src/lib.rs",
    "app_run.rs": "apps/victory/src/run.rs",
    "cpu_trace.rs": "crates/victory-gpu/src/cpu_trace.rs",
}

def preview(files, model, bridge):
    changed = dict(files)
    if "cpu_trace.rs" in changed:
        raise ValueError("cpu_trace.rs already exists")
    for name, old, new in REPLACEMENTS:
        text = changed[name]
        if text.count(old) != 1:
            raise ValueError("missing or ambiguous anchor in " + name)
        changed[name] = text.replace(old, new, 1)
    changed["cpu_trace.rs"] = model.rstrip() + "\n\n" + bridge
    return changed

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared_root", type=Path)
    args = parser.parse_args()
    root = args.prepared_root
    own = Path(__file__).resolve().parents[1]
    files = {name: (root / path).read_text(encoding="utf-8")
             for name, path in SOURCE_PATHS.items() if name != "cpu_trace.rs"}
    if (root / SOURCE_PATHS["cpu_trace.rs"]).exists():
        parser.error("cpu_trace.rs already exists")
    try:
        changed = preview(files, (own / "probes/cpu_trace_buffer.rs").read_text(),
                          (own / "probes/cpu_trace_runtime_bridge.rs").read_text())
    except ValueError as exc:
        parser.error(str(exc))
    for name, text in changed.items():
        prefix = SOURCE_PATHS[name]
        print("".join(difflib.unified_diff(files.get(name, "").splitlines(True),
              text.splitlines(True), fromfile="a/" + prefix if name in files else "/dev/null",
              tofile="b/" + prefix)), end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
