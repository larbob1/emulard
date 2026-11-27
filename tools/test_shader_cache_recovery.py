# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the exact runtime cache policy against deterministic cache faults."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES

STUBS = r'''
extern crate self as anyhow;
extern crate self as tracing;
#[macro_export]
macro_rules! warn { ($($tt:tt)*) => {{}} }
#[macro_export]
macro_rules! debug { ($($tt:tt)*) => {{}} }

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::OnceLock;
use std::path::{Path, PathBuf};
type HostShader = Vec<u8>;
pub type Result<T, E = Error> = std::result::Result<T, E>;
#[derive(Debug)]
pub struct Error(String);
impl Error {
    pub fn msg(s: String) -> Self { Self(s) }
}
impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.0.fmt(f)
    }
}
trait Converter: Send + Sync {
    fn id(&self) -> &'static str;
    fn version(&self) -> u32;
    fn convert(&self, input: &[u8]) -> Result<Vec<u8>>;
}
static MISSES: AtomicU64 = AtomicU64::new(0);
static HITS: AtomicU64 = AtomicU64::new(0);
static DECODES: AtomicU64 = AtomicU64::new(0);
fn encode(s: &HostShader) -> Vec<u8> { s.clone() }
fn decode(s: &[u8]) -> Option<HostShader> {
    DECODES.fetch_add(1, Ordering::Relaxed);
    (s.first() == Some(&7)).then(|| s.to_vec())
}
struct Cache { path: PathBuf, unreadable: bool }
impl Cache {
    fn get_or_convert(&self, c: &dyn Converter, input: &[u8]) -> Result<PathBuf> {
        assert_eq!(c.id(), "shader.dxil");
        assert_eq!(c.version(), 1);
        if self.path.is_file() { return Ok(self.path.clone()); }
        let output = c.convert(input)?;
        if self.unreadable {
            // Successful publication but unreadable on lookup.
            return Ok(self.path.clone());
        }
        std::fs::write(&self.path, output).map_err(|e| Error(e.to_string()))?;
        Ok(self.path.clone())
    }
}
'''

HARNESS = r'''
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let path = Path::new(&args[2]).join("cache-entry");
    let cache = Cache { path: path.clone(), unreadable: args[1] == "unreadable" };
    let runs = AtomicU64::new(0);
    let translate = |_: &[u8]| {
        runs.fetch_add(1, Ordering::Relaxed);
        Ok(vec![7, 8, 9])
    };
    let build = [0u8; 32];
    let expected = Ok(vec![7, 8, 9]);
    match args[1].as_str() {
        "reuse" => {
            assert!(reuse_translated_on());
            assert!(reuse_translated(Some("1")));
            for value in [None, Some(""), Some("0"), Some("true"), Some(" 1")] {
                assert!(!reuse_translated(value));
            }
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(DECODES.load(Ordering::Relaxed), 0);
            assert_eq!(std::fs::read(&path).unwrap(), vec![7, 8, 9]);
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(DECODES.load(Ordering::Relaxed), 1);
            assert_eq!(runs.load(Ordering::Relaxed), 1);
            assert_eq!(MISSES.load(Ordering::Relaxed), 1);
            assert_eq!(HITS.load(Ordering::Relaxed), 1);
        }
        "strict" => {
            assert!(reuse_translated_on());
            assert_eq!(cached_with_policy(&cache, &build, b"x", translate, false), expected);
            assert_eq!(DECODES.load(Ordering::Relaxed), 1);
            assert_eq!(runs.load(Ordering::Relaxed), 1);
        }
        "hit" => {
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(runs.load(Ordering::Relaxed), 1);
            assert_eq!(HITS.load(Ordering::Relaxed), 1);
            assert_eq!(MISSES.load(Ordering::Relaxed), 1);
        }
        "publication" => {
            std::fs::create_dir(&path).unwrap();
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(runs.load(Ordering::Relaxed), 1);
            assert_eq!(MISSES.load(Ordering::Relaxed), 1);
            assert!(path.is_dir());
            std::fs::remove_dir(&path).unwrap();
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(runs.load(Ordering::Relaxed), 2);
        }
        "unsupported" => {
            let fail = |_: &[u8]| {
                runs.fetch_add(1, Ordering::Relaxed);
                Err("unsupported".to_owned())
            };
            assert_eq!(cached(&cache, &build, b"x", fail), Err("unsupported".to_owned()));
            assert_eq!(runs.load(Ordering::Relaxed), 1);
            assert!(!path.exists());
        }
        "warm" => {
            std::fs::create_dir(&path).unwrap();
            assert!(cached_with_policy(&cache, &build, b"x", translate, false).is_err());
            assert_eq!(runs.load(Ordering::Relaxed), 1);
            assert_eq!(MISSES.load(Ordering::Relaxed), 0);
        }
        "unreadable" => {
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(runs.load(Ordering::Relaxed), 1);
            assert!(cached_with_policy(&cache, &build, b"x", translate, false).is_err());
            assert_eq!(runs.load(Ordering::Relaxed), 3);
        }
        "damaged" => {
            std::fs::write(&path, b"bad").unwrap();
            assert_eq!(cached(&cache, &build, b"x", translate), expected);
            assert_eq!(runs.load(Ordering::Relaxed), 1);
            assert_eq!(std::fs::read(&path).unwrap(), vec![7, 8, 9]);
        }
        _ => panic!("unknown test"),
    }
}
'''

@unittest.skipUnless(shutil.which("rustc"), "rustc required for portable shader cache tests")
class ShaderCacheRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.work.cleanup)
        root = Path(cls.work.name)
        block, = [new for old, new in PATCHES["crates/victory-gpu/src/shader_cache.rs"]
                  if old.startswith("struct Translate<F>")]
        source = root / "shader_cache.rs"
        source.write_text(STUBS + block + HARNESS, encoding="utf-8")
        cls.binary = root / "shader-cache-tests.exe"
        subprocess.run(["rustc", "--edition=2021", str(source), "-o", str(cls.binary)],
                       check=True, capture_output=True, text=True)

    def check(self, name, reuse="0"):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, VICTORY_SHADER_CACHE_REUSE_TRANSLATED=reuse)
            subprocess.run([str(self.binary), name, directory], check=True,
                           capture_output=True, text=True, env=env, timeout=15)

    def test_hit(self):
        self.check("hit")

    def test_publication(self):
        self.check("publication")

    def test_unsupported(self):
        self.check("unsupported")

    def test_warm(self):
        self.check("warm")

    def test_unreadable(self):
        self.check("unreadable")

    def test_damaged(self):
        self.check("damaged")

    def test_reuse_cold_then_hit(self):
        self.check("reuse", "1")

    def test_reuse_preserves_offline_verification(self):
        self.check("strict", "1")

    def test_reuse_existing_failure_paths(self):
        for name in ("publication", "unsupported", "warm", "unreadable", "damaged"):
            with self.subTest(name=name):
                self.check(name, "1")
