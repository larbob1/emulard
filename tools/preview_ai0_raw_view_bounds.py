#!/usr/bin/env python3
"""Review-only raw SRV/UAV bounds preview, never registered in runtime builder.

Input must be the exact raw pinned descriptor/host.rs blob. The output is a
new scratch file. Review against fully prepared source before any port.
The separate std-only fixture may be compiled with rustc --edition=2021 --test.
"""
import argparse
import hashlib
from pathlib import Path

PIN = "7970fc5f0c3977bde0a81dbcec1a497384b933bc"
FIXTURE_PATH = Path(__file__).resolve().parent.parent / "probes/raw_view_bounds_review.rs"
MARKER = "fn ai0_raw_view_bounds("
METHODS = (("raw_at", "null_raw_at"), ("raw_uav_at", "null_raw_uav_at"))
LEGACY = "        let elements = (len / 4).clamp(1, u64::from(u32::MAX)) as u32;"
FLAG = """
fn ai0_raw_view_clamp_enabled() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| std::env::var_os("VICTORY_RAW_VIEW_CLAMP")
        .is_some_and(|v| v == "1"))
}
"""

def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
                        usedforsecurity=False).hexdigest()

def preview(data: bytes, fixture: str) -> bytes:
    if git_blob(data) != PIN:
        raise ValueError("unexpected source blob")
    text = data.decode("utf-8")
    if MARKER in text or fixture.count(MARKER) != 1:
        raise ValueError("unexpected helper marker")
    if text.count(LEGACY) != len(METHODS):
        raise ValueError("unexpected legacy count")
    for method, null in METHODS:
        anchor = (
            f"    pub(crate) fn {method}(&self, index: u32, buffer: &ID3D12Resource, offset: u64, len: u64) {{\n"
            "        let Some(host) = host() else { return };\n" + LEGACY
        )
        if text.count(anchor) != 1:
            raise ValueError("ambiguous or absent method anchor")
        replacement = f"""        let elements = if ai0_raw_view_clamp_enabled() {{
            // SAFETY: the caller supplies a live resource, as in the original path.
            let desc = unsafe {{ buffer.GetDesc() }};
            if desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER {{
                self.{null}(index);
                return;
            }}
            let Some((first, count)) = ai0_raw_view_bounds(desc.Width, offset, len) else {{
                self.{null}(index);
                return;
            }};
            debug_assert_eq!(first, offset / 4);
            count
        }} else {{
            (len / 4).clamp(1, u64::from(u32::MAX)) as u32
        }};"""
        text = text.replace(anchor, anchor.removesuffix(LEGACY) + replacement, 1)
    return (text + "\n" + FLAG + "\n" + fixture).encode("utf-8")

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    try:
        result = preview(args.source.read_bytes(), FIXTURE_PATH.read_text(encoding="utf-8"))
        with args.output.open("xb") as dest:
            dest.write(result)
    except (OSError, ValueError) as exc:
        ap.exit(1, f"preview refused: {type(exc).__name__}\n")
    print("Raw view review postimage created; no native validation performed")

if __name__ == "__main__":
    main()
