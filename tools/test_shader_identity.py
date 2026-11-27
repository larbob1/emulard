# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise actual patched shader interning and linked keys with a deterministic hash stub."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES

STUBS = r'''
use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};
static KEPT: [std::sync::atomic::AtomicU64; 4] =
    [const { std::sync::atomic::AtomicU64::new(0) }; 4];

// Test-only stub intentionally produces identical 64-bit display prefixes
// for distinct inputs, so linked cache keys must use all 32 bytes.
mod blake3 {
    pub struct Digest([u8; 32]);
    impl Digest {
        pub fn as_bytes(&self) -> &[u8; 32] { &self.0 }
        pub fn to_hex(&self) -> String {
            self.0.iter().map(|b| format!("{b:02x}")).collect()
        }
    }
    pub fn hash(bytes: &[u8]) -> Digest {
        let mut digest = [0; 32];
        for (i, b) in bytes.iter().enumerate() {
            let pos = 8 + i % 24;
            digest[pos] ^= *b;
        }
        Digest(digest)
    }
}
#[cfg(windows)]
struct Translated;
'''

HARNESS = r'''
#[test]
fn linked_cache_distinguishes_same_display_prefix() {
    let mesh_a = shader("mesh", b"a");
    let mesh_b = shader("mesh", b"b");
    let pixel_a = shader("pixel", b"c");
    let pixel_b = shader("pixel", b"d");
    assert_eq!(mesh_a.hash, mesh_b.hash);
    assert_eq!(pixel_a.hash, pixel_b.hash);
    let key = linked_shader_key(&mesh_a, &pixel_a);
    assert_ne!(key, linked_shader_key(&mesh_b, &pixel_a));
    assert_ne!(key, linked_shader_key(&mesh_a, &pixel_b));
    assert_eq!(key, linked_shader_key(&shader("mesh", b"a"), &shader("pixel", b"c")));
}

#[test]
fn stage_interning_is_thread_safe() {
    let jobs: Vec<_> = (0..16).map(|i| std::thread::spawn(move || {
        shader(if i % 2 == 0 { "vertex" } else { "pixel" }, b"thread-test")
    })).collect();
    let results: Vec<_> = jobs.into_iter().map(|j| j.join().unwrap()).collect();
    for (i, item) in results.iter().enumerate() {
        assert!(Arc::ptr_eq(item, &results[i % 2]));
    }
    assert!(!Arc::ptr_eq(&results[0], &results[1]));
}
'''

@unittest.skipUnless(shutil.which("rustc"), "rustc required for portable shader identity tests")
class ShaderIdentityTests(unittest.TestCase):
    def test_actual_stage_and_linked_keys(self):
        pipeline = PATCHES["crates/victory-gpu/src/pipeline.rs"]
        host = PATCHES["crates/victory-gpu/src/pipeline/host.rs"]
        struct, = [n for o, n in pipeline if o.startswith("/// A shader container")]
        interning, = [n for o, n in pipeline if o.startswith("/// The shared container")]
        native, = [n for o, n in pipeline if "fn pipelines_keep_their_shaders()" in o]
        native = native.split("    #[test]\n    fn pipelines_keep_their_shaders()", 1)[0]
        key, = [n for o, n in host if o.startswith("/// The mesh program")]
        key = key.split("/// The mesh program", 1)[0]
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "identity.rs"
            binary = root / "identity-tests.exe"
            source.write_text(STUBS + struct + interning + key + native + HARNESS,
                              encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn("3 passed; 0 failed", result.stdout)
