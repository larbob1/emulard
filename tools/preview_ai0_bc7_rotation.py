#!/usr/bin/env python3
"""Review-only preview of the BC7 channel selector correction.

Original finding: trustno1-coder/VIctory-NVIDIA commit
6726920a8072fe720f908913248cf7407cae25b4, attributed there to fxceless.
GPL-3.0-or-later upstream. The test fixture here is independently authored.
No builder registration, no in-place writes, no title data.
Pass the exact pinned bcpack.rs and a NEW scratch output filename.
The emitted full-module postimage must be reviewed before native compilation.
"""
import argparse
import hashlib
from pathlib import Path

PIN = "c8d35378df7fab633cc4370a74655b4bd7db9ac7"
CHANGES = (
    ("    let (mode, rot) = (ctrl & 7, usize::from(ctrl >> 3 & 3));", "    let mode = ctrl & 7;\n    let rot = if mode == 4 || mode == 5 {\n        usize::from((ctrl >> 3) & 3)\n    } else {\n        0\n    };"),
    ("    let rot = usize::from(ctrl >> 3 & 3);", "    let rot = if mode == 4 || mode == 5 {\n        usize::from((ctrl >> 3) & 3)\n    } else {\n        0\n    };"),
)
FIXTURE = "\n#[cfg(test)]\nmod ai0_bc7_rotation_regression {\n    use super::*;\n\n    // Explicit endpoint widths including the extra red p-bit when present.\n    const WIDTHS: [[u8; 4]; 8] = [\n        [5, 4, 4, 0], [7, 6, 6, 0], [5, 5, 5, 0], [8, 7, 7, 0],\n        [5, 5, 5, 6], [7, 7, 7, 8], [8, 7, 7, 7], [6, 5, 5, 5],\n    ];\n    const SUBSETS: [u16; 8] = [3, 2, 3, 2, 1, 1, 1, 2];\n\n    fn control(mode: usize, selector: usize) -> u16 {\n        (SUBSETS[mode] << 6) | ((selector as u16) << 3) | mode as u16\n    }\n\n    // Physical output channel -> stored endpoint channel.\n    fn channel(mode: usize, selector: usize, physical: usize) -> usize {\n        if (mode != 4 && mode != 5) || selector == 0 {\n            return physical;\n        }\n        let other = selector - 1;\n        if physical == 3 { other }\n        else if physical == other { 3 }\n        else { physical }\n    }\n\n    #[test]\n    fn precision_all_modes_and_selectors() {\n        for mode in 0..8 {\n            for selector in 0..4 {\n                let expected: [u8; 4] = std::array::from_fn(|c| WIDTHS[mode][channel(mode, selector, c)]);\n                assert_eq!(bc7_precision(control(mode, selector)), expected,\n                    \"mode {mode} selector {selector}\");\n            }\n        }\n    }\n\n    fn pack(mode: usize, selector: usize, widths: [u8; 4]) -> [u8; 16] {\n        let ep = Bc7Ep {\n            ctrl: control(mode, selector),\n            rows: [[0x1000, 0x2000, 0x3000, 0x4000,\n                    0x5000, 0x6000, 0x7000, 0x8000]; 3],\n        };\n        let ix = Bc7Ix { bits: BC7_INDEX[mode], ix: [[0; 16]; 2] };\n        let mut out = [0; 16];\n        bc7_pack(&ep, &ix, widths, &mut out);\n        out\n    }\n\n    #[test]\n    fn nonrotation_modes_ignore_selector_in_packed_output() {\n        for mode in [0usize, 1, 2, 3, 6, 7] {\n            let baseline = pack(mode, 0, WIDTHS[mode]);\n            for selector in 1..4 {\n                // Pass independent widths so the packer's behavior is tested\n                // separately from the precision function.\n                assert_eq!(pack(mode, selector, WIDTHS[mode]), baseline,\n                    \"mode {mode} selector {selector}\");\n            }\n        }\n    }\n\n    #[test]\n    fn rotating_modes_preserve_header_and_endpoint_fields() {\n        for mode in [4usize, 5] {\n            for selector in 0..4 {\n                let widths: [u8; 4] = std::array::from_fn(|c| WIDTHS[mode][channel(mode, selector, c)]);\n                let packed = u128::from_le_bytes(pack(mode, selector, widths));\n                let header = mode + 1;\n                assert_eq!((packed >> header) & 3, selector as u128);\n                let mut offset = header + 2 + usize::from(mode == 4);\n                for physical in 0..4 {\n                    let stored = channel(mode, selector, physical);\n                    let n = WIDTHS[mode][physical];\n                    for end in 0..2 {\n                        let sample = ((2 * stored + end + 1) as u16) << 12;\n                        let expected = u128::from(sample >> (16 - n));\n                        assert_eq!((packed >> offset) & ((1u128 << n) - 1), expected,\n                            \"mode {mode} selector {selector} channel {physical} endpoint {end}\");\n                        offset += usize::from(n);\n                    }\n                }\n            }\n        }\n    }\n}\n"

def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
                        usedforsecurity=False).hexdigest()

def preview(data: bytes) -> bytes:
    if git_blob(data) != PIN:
        raise ValueError("unexpected source blob")
    text = data.decode("utf-8")
    if "mod ai0_bc7_rotation_regression" in text:
        raise ValueError("fixture already present")
    for old, new in CHANGES:
        if text.count(old) != 1:
            raise ValueError("ambiguous or absent source anchor")
        text = text.replace(old, new, 1)
    return (text + "\n" + FIXTURE).encode("utf-8")

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    try:
        original = args.source.read_bytes()
        result = preview(original)
        # Exclusive creation: cannot overwrite any file, including source.
        with args.output.open("xb") as dest:
            dest.write(result)
    except (OSError, ValueError) as exc:
        ap.exit(1, f"preview refused: {type(exc).__name__}\n")
    print("BC7 review postimage created; native tests not run")

if __name__ == "__main__":
    main()
