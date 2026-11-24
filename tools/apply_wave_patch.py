#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply revision-pinned wave retry and shader cache policy candidates."""
import argparse
from pathlib import Path
import sys
from apply_memory_patch import blob_hash

SPECS = [["crates/victory-shader/src/emit/mod.rs","b667241c7012681ea251b523ffba32420c779f28",[["        let forms = [\n            (\"without early-outs\", form(ir::without_early_outs(p))),\n            (\"without skips\", form(ir::without_skips(p, false))),\n        ];","        // Constant-edge threading can resolve a register or a branch that\n        // otherwise prevents an exact split-wave lowering. Try it before\n        // any approximate half-wave fallback, including when the original\n        // emitted successfully but still requested a 64-lane host wave.\n        let edges = threading::constant_edges(p, st);\n        let threaded = if edges.is_empty() {\n            None\n        } else {\n            form(ir::thread_edges(p, &edges).ok())\n        };\n        let forms = [\n            (\"without early-outs\", form(ir::without_early_outs(p))),\n            (\"without skips\", form(ir::without_skips(p, false))),\n            (\"constant-edge threading\", threaded),\n        ];"],["                && std::env::var_os(\"VICTORY_WAVE_WIDE\").is_none_or(|v| v != \"0\") =>","                && allow_wide_retry(native.wave64, std::env::var_os(\"VICTORY_WAVE_WIDE\").as_deref()) =>"],["/// Emits a program whose earlier stages already ran.","/// Keep the fallback policy identical to the main wave64 retry path.\nfn allow_wide_retry(wave64: bool, setting: Option<&std::ffi::OsStr>) -> bool {\n    if wave64 {\n        setting.is_some_and(|v| v == \"1\")\n    } else {\n        setting.is_none_or(|v| v != \"0\")\n    }\n}\n\n#[cfg(test)]\nmod wave_retry_policy_tests {\n    use super::allow_wide_retry;\n    use std::ffi::OsStr;\n\n    #[test]\n    fn wave64_requires_explicit_opt_in() {\n        assert!(!allow_wide_retry(true, None));\n        assert!(!allow_wide_retry(true, Some(OsStr::new(\"0\"))));\n        assert!(!allow_wide_retry(true, Some(OsStr::new(\"other\"))));\n        assert!(allow_wide_retry(true, Some(OsStr::new(\"1\"))));\n    }\n\n    #[test]\n    fn wave32_preserves_existing_default() {\n        assert!(allow_wide_retry(false, None));\n        assert!(!allow_wide_retry(false, Some(OsStr::new(\"0\"))));\n        assert!(allow_wide_retry(false, Some(OsStr::new(\"1\"))));\n    }\n}\n\n/// Emits a program whose earlier stages already ran."]]],["crates/victory-gpu/src/shader_cache.rs","eabd0f3fae4a0bb35c15b84913255a82918f884b",[["                    \"VICTORY_WAVE_WIDE\",\n","                    \"VICTORY_WAVE_WIDE\",\n                    \"VICTORY_WAVE_LOCAL\",\n"]]]]

def patch_source(data, expected, edits):
    normalized = data.replace(b"\r\n", b"\n")
    if blob_hash(normalized) != expected:
        raise ValueError("Wave source differs from reviewed blob.")
    result = normalized.decode("utf-8")
    for before, after in edits:
        if result.count(before) != 1:
            raise ValueError("Wave source anchor differs.")
        result = result.replace(before, after)
    updated = result.encode("utf-8")
    return updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkout", type=Path)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    root = args.checkout.resolve()
    try:
        if not (root / ".git").exists():
            raise ValueError("Use a separate Git checkout.")
        pending = {}
        for path, expected, edits in SPECS:
            target = root / path
            if target.resolve() != target or not target.is_file():
                raise ValueError("Invalid source path.")
            pending[target] = patch_source(target.read_bytes(), expected, edits)
        if args.apply:
            for target, data in pending.items():
                target.write_bytes(data)
            print("Wave candidates applied.")
        else:
            print("Wave sources validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
