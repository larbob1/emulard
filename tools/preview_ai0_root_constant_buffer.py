# SPDX-License-Identifier: GPL-3.0-or-later
"""Review-only root constant buffer preview; no production registration."""
import argparse
import hashlib
from pathlib import Path

PIN = "41380c23a61b93000c4886265c3063676ddc4864"
START = "    pub(crate) fn bind(&mut self, list: &HostList, p: &HostPipeline, compute: bool) -> bool {"
END = "\n    }\n\n    /// Binds a root UAV:"
OLD = "            if let Some((param, dwords)) = stage.user_data {\n                let mut values = vec![0u32; dwords as usize];\n                for u in &t.host.user_data {\n                    if let RootType::Other(kind) = u.root {\n                        values[u.index as usize] =\n                            self.host_word(compute, kind, u.slot, u.dword, memory.as_ref());\n                        continue;\n                    }\n                    let fresh = made\n                        .iter()\n                        .find(|m| m.0 == u.slot && u.root == RootType::Table);\n                    values[u.index as usize] = match fresh {\n                        Some(&(_, offset)) => offset,\n                        None => self.user_value(compute, u.slot, u.root, u.dword),\n                    };\n                }\n                // SAFETY: an open list; `values` covers the parameter.\n                unsafe {\n                    if compute {\n                        l.SetComputeRoot32BitConstants(param, dwords, values.as_ptr().cast(), 0);\n                    } else {\n                        l.SetGraphicsRoot32BitConstants(param, dwords, values.as_ptr().cast(), 0);\n                    }\n                }\n            }\n"
NEW = "            if let Some((param, dwords)) = stage.user_data {\n                let len = dwords as usize;\n                let mut inline = [0u32; 64];\n                let mut overflow;\n                let values = if len <= inline.len() {\n                    &mut inline[..len]\n                } else {\n                    overflow = vec![0u32; len];\n                    overflow.as_mut_slice()\n                };\n                for u in &t.host.user_data {\n                    if let RootType::Other(kind) = u.root {\n                        values[u.index as usize] =\n                            self.host_word(compute, kind, u.slot, u.dword, memory.as_ref());\n                        continue;\n                    }\n                    let fresh = made\n                        .iter()\n                        .find(|m| m.0 == u.slot && u.root == RootType::Table);\n                    values[u.index as usize] = match fresh {\n                        Some(&(_, offset)) => offset,\n                        None => self.user_value(compute, u.slot, u.root, u.dword),\n                    };\n                }\n                // SAFETY: an open list; `values` covers the parameter.\n                unsafe {\n                    if compute {\n                        l.SetComputeRoot32BitConstants(param, dwords, values.as_ptr().cast(), 0);\n                    } else {\n                        l.SetGraphicsRoot32BitConstants(param, dwords, values.as_ptr().cast(), 0);\n                    }\n                }\n            }\n"


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def clone(source):
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("bind method boundary mismatch")
    a = source.index(START)
    b = source.index(END, a) + len("\n    }")
    method = source[a:b]
    if method.count(OLD) != 1 or "bind_inline_constants" in source:
        raise ValueError("constant block anchor or prior candidate mismatch")
    return method.replace(START, START.replace("pub(crate) fn bind(", "fn bind_inline_constants("), 1).replace(OLD, NEW, 1)


def preview(source, expected=PIN):
    if blob(source) != expected:
        raise ValueError("draw source blob mismatch")
    return source + b"\n#[cfg(test)]\nimpl State {\n" + clone(source.decode()).encode() + b"\n}\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    data = preview(a.source.read_bytes())
    with a.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
