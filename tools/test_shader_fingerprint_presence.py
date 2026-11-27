# SPDX-License-Identifier: GPL-3.0-or-later
"""Fresh-process review proof of shader fingerprint framing, not a runtime patch."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

NAMES = ("VICTORY_MESH_OUTPUT_STRICT", "VICTORY_STRICT_JOINS")
# Old loop copied from pinned emit/mod.rs (282d7c0757c70b2a71c58bd989191962314d55e1).
# Supply only the two generated switch names, not the complete translator.
SOURCE = r'''
fn legacy(names: &[&str]) -> Vec<u8> {
    let mut out = Vec::new();
    for name in names {
        out.extend_from_slice(name.as_bytes());
        out.push(b'=');
        if let Some(value) = std::env::var_os(name) {
            out.extend_from_slice(value.as_encoded_bytes());
        }
        out.push(0);
    }
    out
}

// Proposed review-only framing. Every field is unambiguously delimited.
// A fixed u64 length is portable across target pointer widths.
fn framed(names: &[&str]) -> Vec<u8> {
    let mut out = Vec::new();
    for name in names {
        out.extend_from_slice(&(name.len() as u64).to_le_bytes());
        out.extend_from_slice(name.as_bytes());
        match std::env::var_os(name) {
            None => out.push(0),
            Some(value) => {
                out.push(1);
                let bytes = value.as_encoded_bytes();
                out.extend_from_slice(&(bytes.len() as u64).to_le_bytes());
                out.extend_from_slice(bytes);
            }
        }
    }
    out
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn main() {
    let names = ["VICTORY_MESH_OUTPUT_STRICT", "VICTORY_STRICT_JOINS"];
    // Only generated environment values are supplied by the parent fixture.
    println!("legacy={}", hex(&legacy(&names)));
    println!("framed={}", hex(&framed(&names)));
    println!("presence={}{}", u8::from(std::env::var_os(names[0]).is_some()),
             u8::from(std::env::var_os(names[1]).is_some()));
}
'''


@unittest.skipUnless(shutil.which("rustc"), "Rust compiler unavailable")
class ShaderFingerprintPresenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        source = Path(cls.tmp.name) / "fingerprint.rs"
        cls.exe = Path(cls.tmp.name) / "fingerprint.exe"
        source.write_text(SOURCE, encoding="utf-8")
        subprocess.run(["rustc", "--edition=2021", str(source), "-o", str(cls.exe)],
                       check=True, capture_output=True, timeout=45)

    def receipt(self, left, right):
        env = {key: value for key, value in os.environ.items()
               if key.upper() not in NAMES}
        for key, value in zip(NAMES, (left, right)):
            if value is not None:
                env[key] = value
        result = subprocess.run([str(self.exe)], env=env, check=True,
                                capture_output=True, text=True, timeout=10)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 3)
        fields = dict(line.split("=", 1) for line in lines)
        self.assertEqual(set(fields), {"legacy", "framed", "presence"})
        self.assertEqual(fields["presence"], "".join(
            "0" if value is None else "1" for value in (left, right)))
        return bytes.fromhex(fields["legacy"]), bytes.fromhex(fields["framed"])

    def test_actual_legacy_unset_empty_collision(self):
        absent = self.receipt(None, None)
        for left, right in (("", None), (None, ""), ("", "")):
            with self.subTest(left=left, right=right):
                actual = self.receipt(left, right)
                self.assertEqual(actual[0], absent[0])
                self.assertNotEqual(actual[1], absent[1])

    def test_framing_distinguishes_all_state_pairs(self):
        states = (None, "", "0", "1", "=", "VICTORY_STRICT_JOINS=1")
        seen = set()
        for left in states:
            for right in states:
                framed = self.receipt(left, right)[1]
                self.assertNotIn(framed, seen)
                seen.add(framed)
        self.assertEqual(len(seen), 36)

    def test_exact_framed_encoding_and_determinism(self):
        def field(name, value):
            encoded = name.encode("ascii")
            prefix = len(encoded).to_bytes(8, "little") + encoded
            if value is None:
                return prefix + b"\x00"
            raw = value.encode("ascii")
            return prefix + b"\x01" + len(raw).to_bytes(8, "little") + raw
        for left, right in ((None, ""), ("a=b", "0"), ("", None)):
            expected = field(NAMES[0], left) + field(NAMES[1], right)
            self.assertEqual(self.receipt(left, right)[1], expected)
            self.assertEqual(self.receipt(left, right)[1], expected)
        print("Shader fingerprint presence proof: legacy collision; 36 distinct framed states (separate test)")
