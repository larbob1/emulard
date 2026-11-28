# SPDX-License-Identifier: GPL-3.0-or-later
"""R2 isolated repair transformation. No file writes or production registration.
Input: exact LF-normalized paired-wave prepared source. The caller must verify
its disposable checkout, upstream, manifests, inventory and fixture pins.
"""
import hashlib


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


PINS = {
    "host.rs": ("88acbb3b2cf550cdf2303685fcc32249f9e46328", "031a65c12bbab967759383b2a75a3be46c46bbde"),
    "texback.rs": ("3102a4f9ed2f80c86a28fcc5070b855143279574", "a17dfb5f693163d64ab8f4a60ede71e52c2f596a"),
}

REPLACEMENTS = {
    "host.rs": [("        let mut deferred = self.deferred();\n        if !deferred.back_wanted.iter().any(|target| target.owner() == resource as usize)\n            && let Some(target) = crate::texback::Target::new(resource)\n        {\n            deferred.back_wanted.push(target);\n        }\n", "        let replaced = {\n            let mut deferred = self.deferred();\n            if let Some(index) = deferred.back_wanted.iter().position(|target| target.owner() == resource as usize) {\n                if deferred.back_wanted[index].is_current() {\n                    None\n                } else {\n                    crate::texback::Target::new(resource)\n                        .map(|target| std::mem::replace(&mut deferred.back_wanted[index], target))\n                }\n            } else {\n                if let Some(target) = crate::texback::Target::new(resource) {\n                    deferred.back_wanted.push(target);\n                }\n                None\n            }\n        };\n        // Drop an obsolete host copy outside the deferred-list guard.\n        drop(replaced);\n")],
    "texback.rs": [("    let end = at.saturating_add(len);\n    invalidate(|ticket| at < ticket.end && ticket.at < end);\n", "    let end = at.saturating_add(len);\n    if end <= at {\n        return;\n    }\n    invalidate(|ticket| at < ticket.end && ticket.at < end);\n"),
                   ("    pub(crate) fn owner(&self) -> usize { self.ticket.owner }\n", "    pub(crate) fn owner(&self) -> usize { self.ticket.owner }\n\n    pub(crate) fn is_current(&self) -> bool {\n        self.ticket.valid.load(Ordering::Acquire)\n    }\n")],
}


def replace_once(data, old, new):
    old, new = old.encode(), new.encode()
    if data.count(old) != 1:
        raise ValueError("nonunique R2 repair anchor")
    return data.replace(old, new, 1)


def transform(name, prepared):
    before, after = PINS[name]
    if blob(prepared) != before:
        raise ValueError("incorrect prepared R2 source: " + name)
    result = prepared
    for old, new in REPLACEMENTS[name]:
        result = replace_once(result, old, new)
    if blob(result) != after:
        raise ValueError("incorrect R2 repair postimage: " + name)
    inverse = result
    for old, new in reversed(REPLACEMENTS[name]):
        inverse = replace_once(inverse, new, old)
    if inverse != prepared:
        raise ValueError("R2 repair inverse mismatch: " + name)
    return result
