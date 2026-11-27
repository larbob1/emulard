# SPDX-License-Identifier: GPL-3.0-or-later
"""Test the actual extracted memo logic without a graphics device."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from apply_pipeline_perf import PATCHES


def postimage():
    patch, = [new for _, new in PATCHES["crates/victory-gpu/src/shader_cache.rs"]
              if "struct BuildFingerprintMemo" in new]
    return patch


class ShaderBuildMemoTests(unittest.TestCase):
    def test_exact_key_inputs_and_fallback(self):
        source = postimage()
        self.assertLess(source.index("let fingerprint = victory_shader::emit::translation_fingerprint()"),
                        source.index("BUILD_MEMO.try_with"))
        self.assertIn("memo.try_borrow_mut().ok()", source)
        self.assertIn("hash_build(*exe, &fingerprint)", source)
        self.assertIn('std::env::var_os("VICTORY_SHADER_BUILD_MEMO").is_some_and(|v| v == "1")', source)
        self.assertIn('h.update(include_bytes!("shader_cache.rs"))', source)
        self.assertIn("saved.as_slice() == fingerprint", source)

    def test_actual_build_fixture_wiring(self):
        source = postimage()
        fixture = source.split("fn actual_build_memo_modes_and_tls_fallback()", 1)[1].split(
            "fn oversized_fingerprint_is_not_retained()", 1)[0]
        self.assertIn('matches!(mode.as_str(), "0" | "1")', fixture)
        self.assertIn("Restore(view_heap_limit())", fixture)
        self.assertIn("set_view_heap_limit(64)", fixture)
        self.assertIn("set_view_heap_limit(128)", fixture)
        self.assertIn("let held = m.borrow_mut()", fixture)
        self.assertIn("assert_eq!(held.last, previous)", fixture)
        self.assertIn("assert_eq!(b, reference())", fixture)
        self.assertIn("scope.spawn", fixture)
        self.assertIn("assert_eq!(m.borrow().last.is_some(), enabled)", fixture)
        self.assertNotIn("set_var(", fixture)
        self.assertNotIn("emit::translate(", fixture)
        self.assertIn('#[ignore = "fresh process;', source)

    def test_actual_build_measurement_wiring(self):
        source = postimage()
        fixture = source.split("fn shader_build_memo_measurement()", 1)[1].split(
            "fn oversized_fingerprint_is_not_retained()", 1)[0]
        self.assertIn("const CALLS: usize = 2048", fixture)
        self.assertIn("for repeat in 0..4", fixture)
        self.assertIn("for churn in [repeat % 2 == 1, repeat % 2 == 0]", fixture)
        self.assertIn("BUILD_MEMO.with(|m| m.borrow_mut().last = None)", fixture)
        self.assertIn("results.push(black_box(build()))", fixture)
        self.assertIn("assert_eq!(key, if churn && i % 2 == 0 { b } else { a })", fixture)
        self.assertIn("if repeat != 0", fixture)
        self.assertIn("elapsed_ns={}", fixture)
        self.assertNotIn("emit::translate(", fixture)
        self.assertNotIn("set_var(", fixture)
        self.assertIn('#[ignore = "isolated release-mode build digest measurement"]', source)

    @unittest.skipUnless(shutil.which("rustc"), "Rust compiler unavailable")
    def test_extracted_memo_logic(self):
        source = postimage().split("const BUILD_MEMO_MAX:", 1)[1].split("thread_local!", 1)[0]
        source = "const BUILD_MEMO_MAX:" + source
        tests = r"""
#[test]
fn memo_matches_all_inputs() {
    let mut memo = BuildFingerprintMemo::default();
    assert_eq!(memo.get_or_hash(None, b"abc", || [1; 32]), [1; 32]);
    assert_eq!(memo.get_or_hash(None, b"abc", || panic!("rehashed")), [1; 32]);
    assert_eq!(memo.get_or_hash(None, b"abd", || [2; 32]), [2; 32]);
    assert_eq!(memo.get_or_hash(Some([3; 32]), b"abd", || [3; 32]), [3; 32]);
    assert_eq!(memo.get_or_hash(None, b"abd", || [4; 32]), [4; 32]);
}

#[test]
fn oversize_and_one_entry() {
    let mut memo = BuildFingerprintMemo::default();
    let large = vec![0; BUILD_MEMO_MAX + 1];
    let small = vec![0; BUILD_MEMO_MAX];
    assert_eq!(memo.get_or_hash(None, &small, || [1; 32]), [1; 32]);
    assert!(memo.last.is_some());
    assert_eq!(memo.get_or_hash(None, &large, || [2; 32]), [2; 32]);
    assert!(memo.last.is_none());
    assert_eq!(memo.get_or_hash(None, &large, || [3; 32]), [3; 32]);
    assert_eq!(memo.get_or_hash(None, &small, || [4; 32]), [4; 32]);
}

#[test]
fn independent_instances() {
    let mut a = BuildFingerprintMemo::default();
    let mut b = BuildFingerprintMemo::default();
    assert_eq!(a.get_or_hash(None, b"x", || [1; 32]), [1; 32]);
    assert_eq!(b.get_or_hash(None, b"x", || [2; 32]), [2; 32]);
    assert_eq!(a.get_or_hash(None, b"x", || panic!("rehashed")), [1; 32]);
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memo.rs"
            exe = Path(tmp) / "memo-test.exe"
            path.write_text(source + tests, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(path), "-o", str(exe)],
                           check=True, capture_output=True, text=True, timeout=45)
            result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=10)
            self.assertIn("3 passed; 0 failed", result.stdout)
            print("Shader build memo Rust proof: 3 passed; 0 failed")
