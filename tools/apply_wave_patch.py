#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply revision-pinned wave retry and shader cache policy candidates."""
import argparse
from pathlib import Path
import sys
from apply_memory_patch import blob_hash

SPECS = [["crates/victory-shader/src/emit/mod.rs","b667241c7012681ea251b523ffba32420c779f28",[["        let forms = [\n            (\"without early-outs\", form(ir::without_early_outs(p))),\n            (\"without skips\", form(ir::without_skips(p, false))),\n        ];","        // Constant-edge threading can resolve a register or a branch that\n        // otherwise prevents an exact split-wave lowering. Try it before\n        // any approximate half-wave fallback, including when the original\n        // emitted successfully but still requested a 64-lane host wave.\n        let edges = threading::constant_edges(p, st);\n        let threaded = if edges.is_empty() {\n            None\n        } else {\n            form(ir::thread_edges(p, &edges).ok())\n        };\n        let forms = [\n            (\"without early-outs\", form(ir::without_early_outs(p))),\n            (\"without skips\", form(ir::without_skips(p, false))),\n            (\"constant-edge threading\", threaded),\n        ];"],["                && std::env::var_os(\"VICTORY_WAVE_WIDE\").is_none_or(|v| v != \"0\") =>","                && allow_wide_retry(native.wave64, std::env::var_os(\"VICTORY_WAVE_WIDE\").as_deref()) =>"],["/// Emits a program whose earlier stages already ran.","/// Keep the fallback policy identical to the main wave64 retry path.\nfn allow_wide_retry(wave64: bool, setting: Option<&std::ffi::OsStr>) -> bool {\n    if wave64 {\n        setting.is_some_and(|v| v == \"1\")\n    } else {\n        setting.is_none_or(|v| v != \"0\")\n    }\n}\n\n#[cfg(test)]\nmod wave_retry_policy_tests {\n    use super::allow_wide_retry;\n    use std::ffi::OsStr;\n\n    #[test]\n    fn wave64_requires_explicit_opt_in() {\n        assert!(!allow_wide_retry(true, None));\n        assert!(!allow_wide_retry(true, Some(OsStr::new(\"0\"))));\n        assert!(!allow_wide_retry(true, Some(OsStr::new(\"other\"))));\n        assert!(allow_wide_retry(true, Some(OsStr::new(\"1\"))));\n    }\n\n    #[test]\n    fn wave32_preserves_existing_default() {\n        assert!(allow_wide_retry(false, None));\n        assert!(!allow_wide_retry(false, Some(OsStr::new(\"0\"))));\n        assert!(allow_wide_retry(false, Some(OsStr::new(\"1\"))));\n    }\n}\n\n/// Emits a program whose earlier stages already ran."],["pub use lower::set_host_max_wave;","pub use lower::set_host_max_wave;\n\n/// Host lane capability used by the translation cache.\npub fn host_wave_limit() -> u32 {\n    lower::host_max_wave()\n}"],["                    let bases = [\n                        deep.as_ref().map(|f| &f.0),\n                        forms[1].1.as_ref().map(|f| &f.0),\n                        forms[0].1.as_ref().map(|f| &f.0),\n                        Some(p),\n                    ];\n                    if let Some(base) = bases.into_iter().flatten().next() {","                    // The first available form need not be the one whose\n                    // branches can safely be widened. Try each distinct form,\n                    // including the constant-edge-threaded program.\n                    let bases = [\n                        deep.as_ref().map(|f| &f.0),\n                        forms[2].1.as_ref().map(|f| &f.0),\n                        forms[1].1.as_ref().map(|f| &f.0),\n                        forms[0].1.as_ref().map(|f| &f.0),\n                        Some(p),\n                    ];\n                    for base in bases.into_iter().flatten() {"],["        let strict = std::env::var_os(\"VICTORY_WAVE_LOCAL\").is_some_and(|v| v == \"idiom\");","        // Spilled compute programs include the dynamic structure builder.\n        // Never use an unproven half-wave approximation for these programs.\n        let strict = crate::spill::is_spilled(native)\n            || std::env::var_os(\"VICTORY_WAVE_LOCAL\").is_some_and(|v| v == \"idiom\");"]]],["crates/victory-gpu/src/shader_cache.rs","eabd0f3fae4a0bb35c15b84913255a82918f884b",[["                    \"VICTORY_WAVE_WIDE\",\n","                    \"VICTORY_WAVE_WIDE\",\n                    \"VICTORY_WAVE_LOCAL\",\n"],["        Some(cache) => cached(cache, build(), container, translate),","        Some(cache) => {\n            let key = wave_build_key(build(), victory_shader::emit::host_wave_limit());\n            cached(cache, &key, container, translate)\n        }"],["/// The translation of a console shader container, from the cache when","/// The executable fingerprint already distinguishes different feedback\n/// layouts. Add the host lane capability at lookup time, after device\n/// initialization, rather than capturing it in the static build key.\nfn wave_build_key(build: &[u8; 32], lanes: u32) -> [u8; 32] {\n    let mut hasher = blake3::Hasher::new();\n    hasher.update(b\"emulard-wave-cache-v1\");\n    hasher.update(build);\n    hasher.update(&lanes.to_le_bytes());\n    *hasher.finalize().as_bytes()\n}\n\n#[cfg(test)]\nmod wave_cache_key_tests {\n    use super::wave_build_key;\n    #[test]\n    fn host_capability_changes_the_cache_key() {\n        let build = [1; 32];\n        let a = wave_build_key(&build, 32);\n        assert_eq!(a, wave_build_key(&build, 32));\n        assert_ne!(a, wave_build_key(&build, 64));\n        assert_ne!(a, wave_build_key(&build, 0));\n        assert_ne!(a, wave_build_key(&[2; 32], 32));\n    }\n}\n\n/// The translation of a console shader container, from the cache when"]]]]

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
