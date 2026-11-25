#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Avoid deep Rust recursion when emitting console lane predicates."""
import argparse
from pathlib import Path
import sys

BEFORE = '''    fn boolean(&mut self, b: Bool, at: usize) -> Result<V, Why> {
        if b == Bool::TRUE || b == Bool::FALSE {
            return Ok(self.s.m.bool(b == Bool::TRUE));
        }
        if let Some(&v) = self.bools.get(&(at, b)) {
            return Ok(v);
        }
        let (atom, lo, hi) = self.x.st.bools.node(b).expect("not a constant");
        let a = self.atom(atom, at)?;
        let m = &mut self.s.m;
        let v = match (lo, hi) {
            (Bool::FALSE, Bool::TRUE) => a,
            (Bool::TRUE, Bool::FALSE) => {
                let t = m.bool(true);
                m.bin(at, Bin::Xor, a, t)
            }
            (Bool::FALSE, h) => {
                let h = self.boolean(h, at)?;
                self.s.m.bin(at, Bin::And, a, h)
            }
            (l, Bool::TRUE) => {
                let l = self.boolean(l, at)?;
                self.s.m.bin(at, Bin::Or, a, l)
            }
            (l, h) => {
                let l = self.boolean(l, at)?;
                let h = self.boolean(h, at)?;
                self.s.m.select(at, a, h, l)
            }
        };
        self.bools.insert((at, b), v);
        Ok(v)
    }
'''

AFTER = '''    fn boolean(&mut self, b: Bool, at: usize) -> Result<V, Why> {
        if b == Bool::TRUE || b == Bool::FALSE {
            return Ok(self.s.m.bool(b == Bool::TRUE));
        }
        if let Some(&v) = self.bools.get(&(at, b)) {
            return Ok(v);
        }

        // Predicate BDDs can be very deep for large console shaders. Emit
        // them in post-order so shader complexity does not consume Rust stack.
        let mut pending = vec![(b, false)];
        while let Some((node, expanded)) = pending.pop() {
            if node == Bool::TRUE || node == Bool::FALSE || self.bools.contains_key(&(at, node)) {
                continue;
            }
            let (atom, lo, hi) = self.x.st.bools.node(node).expect("not a constant");
            if !expanded {
                pending.push((node, true));
                for child in [lo, hi] {
                    if child != Bool::TRUE && child != Bool::FALSE
                        && !self.bools.contains_key(&(at, child))
                    {
                        pending.push((child, false));
                    }
                }
                continue;
            }

            let a = self.atom(atom, at)?;
            let value = |this: &mut Self, child: Bool| -> Result<V, Why> {
                match child {
                    Bool::FALSE => Ok(this.s.m.bool(false)),
                    Bool::TRUE => Ok(this.s.m.bool(true)),
                    _ => this.bools.get(&(at, child)).copied().ok_or("a lane predicate dependency"),
                }
            };
            let v = match (lo, hi) {
                (Bool::FALSE, Bool::TRUE) => a,
                (Bool::TRUE, Bool::FALSE) => {
                    let t = self.s.m.bool(true);
                    self.s.m.bin(at, Bin::Xor, a, t)
                }
                (Bool::FALSE, h) => {
                    let h = value(self, h)?;
                    self.s.m.bin(at, Bin::And, a, h)
                }
                (l, Bool::TRUE) => {
                    let l = value(self, l)?;
                    self.s.m.bin(at, Bin::Or, a, l)
                }
                (l, h) => {
                    let l = value(self, l)?;
                    let h = value(self, h)?;
                    self.s.m.select(at, a, h, l)
                }
            };
            self.bools.insert((at, node), v);
        }
        self.bools.get(&(at, b)).copied().ok_or("a lane predicate dependency")
    }
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.checkout.resolve() / "crates/victory-shader/src/emit/lower.rs"
    try:
        data = target.read_bytes()
        normalized = data.replace(b"\r\n", b"\n")
        before, after = BEFORE.encode(), AFTER.encode()
        if normalized.count(before) == 1:
            updated = normalized.replace(before, after)
        elif normalized.count(after) == 1:
            print("Iterative predicate patch is already present.")
            return 0
        else:
            raise ValueError("Lane predicate source anchor differs.")
        if args.apply:
            target.write_bytes(updated.replace(b"\n", b"\r\n") if b"\r\n" in data else updated)
            print("Iterative predicate patch applied.")
        else:
            print("Lane predicate source validated; dry run only.")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
