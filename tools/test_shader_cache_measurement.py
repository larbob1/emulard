# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify that the ignored native cache timing fixture is wired conservatively."""
import unittest
from apply_pipeline_perf import PATCHES


class ShaderCacheMeasurementTests(unittest.TestCase):
    def test_native_measurement_scope(self):
        patch, = [new for _, new in PATCHES["crates/victory-gpu/src/shader_cache.rs"]
                  if "fn shader_cache_reuse_measurement()" in new]
        fixture = patch.split("fn shader_cache_reuse_measurement()", 1)[1].split(
            "fn shader_cache_publication_failure_keeps_runtime_translation()", 1)[0]
        self.assertIn('matches!(mode.as_str(), "0" | "1")', fixture)
        self.assertIn("assert_eq!(reuse_translated_on(), mode == \"1\")", fixture)
        self.assertIn("const N: usize = 16", fixture)
        self.assertIn("for bytes in [4096usize, 65536, 262144]", fixture)
        self.assertIn("for repeat in 0..4", fixture)
        self.assertIn("tempfile::tempdir()", fixture)
        self.assertIn("cold.push(cached(", fixture)
        self.assertIn("warm.push(cached(", fixture)
        self.assertEqual(fixture.count("assert_eq!(runs.load(Ordering::Relaxed), N as u64)"), 2)
        self.assertIn("assert_eq!(std::fs::read(file).unwrap(), encoded)", fixture)
        self.assertIn("if repeat != 0", fixture)
        self.assertIn("cold_ns={} warm_ns={}", fixture)
        self.assertNotIn("emit::translate(", fixture)
        self.assertNotIn("host()", fixture)
        self.assertIn('#[ignore = "bounded release-mode shader cache measurement"]', patch)
