#!/usr/bin/env python3
"""Preview-only EXT-04 heap instance identity correction.

Read exact raw source from a supplied victory-gpu/src directory, verify every
Git blob and anchor, then write a new scratch directory. Never modify input.
Not registered in the runtime builder. Review against fully prepared source.
"""
import argparse
import hashlib
import json
from pathlib import Path

SPECS = json.loads("[{\"path\":\"descriptor/host.rs\",\"pin\":\"7970fc5f0c3977bde0a81dbcec1a497384b933bc\",\"changes\":[[\"pub(crate) struct HostHeap {\\n\",\"pub(crate) struct HostHeap {\\n    ai0_generation: u64,\\n\",1],[\"        let h = HostHeap {\\n\",\"        let h = HostHeap {\\n            ai0_generation: ai0_next_heap_generation(&AI0_NEXT_HEAP_GENERATION)?,\\n\",1],[\"    pub(crate) fn release(&self, first: u32, n: u32) {\",\"    pub(crate) fn ai0_generation(&self) -> u64 {\\n        self.ai0_generation\\n    }\\n\\n    pub(crate) fn ai0_matches_generation(&self, recorded: u64) -> bool {\\n        ai0_same_heap_generation(recorded, self.ai0_generation)\\n    }\\n\\n    pub(crate) fn release(&self, first: u32, n: u32) {\",1]]},{\"path\":\"descriptor.rs\",\"pin\":\"c96ff17e044d5dcfef6ae7897958365aaba73bd0\",\"changes\":[[\"pub(crate) fn release_dynamic(heap: usize, first: u32, n: u32) {\",\"pub(crate) fn release_dynamic(heap: usize, generation: u64, first: u32, n: u32) {\",1],[\"        host.release(first, n);\",\"        if host.ai0_matches_generation(generation) {\\n            host.release(first, n);\\n        }\",1]]},{\"path\":\"draw.rs\",\"pin\":\"41380c23a61b93000c4886265c3063676ddc4864\",\"changes\":[[\"    /// The dynamic slots the list holds: title heap, first, count; given\",\"    /// The dynamic slots the list holds: title heap, host generation, first, count; given\",1],[\"    dynamic: Vec<(usize, u32, u32)>,\",\"    dynamic: Vec<(usize, u64, u32, u32)>,\",1],[\"for &(heap, first, n) in &self.dynamic\",\"for &(heap, generation, first, n) in &self.dynamic\",1],[\"for (heap, first, n) in self.dynamic.drain(..)\",\"for (heap, generation, first, n) in self.dynamic.drain(..)\",1],[\"crate::descriptor::release_dynamic(heap, first, n);\",\"crate::descriptor::release_dynamic(heap, generation, first, n);\",2],[\"self.dynamic.push((key.0, index, 1));\",\"self.dynamic.push((key.0, host.ai0_generation(), index, 1));\",2],[\".push((std::ptr::from_ref(heap) as usize, first, n));\",\".push((std::ptr::from_ref(heap) as usize, host.ai0_generation(), first, n));\",1]]}]")
FIXTURE = Path(__file__).resolve().parent.parent / "probes/heap_generation_review.rs"
MARKER = "fn ai0_next_heap_generation("

def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
                        usedforsecurity=False).hexdigest()

def preview(source: Path, fixture: str) -> dict[str, bytes]:
    if fixture.count(MARKER) != 1:
        raise ValueError("unexpected fixture")
    outputs = {}
    for spec in SPECS:
        name = spec["path"]
        data = (source / name).read_bytes()
        if git_blob(data) != spec["pin"]:
            raise ValueError("unexpected source blob: " + name)
        text = data.decode("utf-8")
        if "ai0_generation" in text or MARKER in text:
            raise ValueError("already modified")
        for old, new, count in spec["changes"]:
            if text.count(old) != count:
                raise ValueError("unexpected anchor count: " + name)
            text = text.replace(old, new)
        if name == "descriptor/host.rs":
            # Separate module avoids import conflicts with the host file.
            text += ("\nmod ai0_heap_generation_review {\n" + fixture
                     + "\n}\n"
                     "use ai0_heap_generation_review::{ai0_next_heap_generation, ai0_same_heap_generation};\n"
                     "static AI0_NEXT_HEAP_GENERATION: std::sync::atomic::AtomicU64 = "
                     "std::sync::atomic::AtomicU64::new(1);\n")
            # Expose only the two pure helpers to the parent module.
            text = text.replace("fn ai0_next_heap_generation(", "pub(super) fn ai0_next_heap_generation(", 1)
            text = text.replace("fn ai0_same_heap_generation(", "pub(super) fn ai0_same_heap_generation(", 1)
        outputs[name] = text.encode("utf-8")
    return outputs

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        outputs = preview(args.source, FIXTURE.read_text(encoding="utf-8"))
        # No exist_ok and no overwrites: even if output aliases input, refuse.
        args.output.mkdir()
        for name, data in outputs.items():
            target = args.output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as dest:
                dest.write(data)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"preview refused: {type(exc).__name__}\n")
    print("Three review postimages created; native validation not performed")

if __name__ == "__main__":
    main()
