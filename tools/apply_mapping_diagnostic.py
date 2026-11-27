#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install an isolated diagnostic-only mapped-view producer on the frozen paired source."""
import argparse
from pathlib import Path

PATH = Path("crates/victory-hle/src/modules/xmem.rs")
REPLACEMENTS = (
    ("    views: BTreeMap<usize, (usize, Slice)>,", "    views: BTreeMap<usize, (usize, Slice)>,\n    mapping_observation: mapping_diagnostic::Working,", 1),
    ("        next_page: 0x10_0000,\n        ..Default::default()", "        next_page: 0x10_0000,\n        mapping_observation: mapping_diagnostic::Working::new(mapping_diagnostic_on()),\n        ..Default::default()", 1),
    ("fn physical() -> MutexGuard<'static, Physical> {\n    PHYSICAL.lock().unwrap_or_else(|e| e.into_inner())\n}", "#[path = \"xmem_mapping_diagnostic.rs\"]\nmod mapping_diagnostic;\n\nstatic MAPPING_PUBLICATION: LazyLock<mapping_diagnostic::Publication> =\n    LazyLock::new(mapping_diagnostic::Publication::default);\n\nfn mapping_diagnostic_on() -> bool {\n    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();\n    cfg!(feature = \"diagnostics\") && *ON.get_or_init(|| std::env::var_os(\"VICTORY_MAPPING_DIAGNOSTIC\").is_some_and(|v| v == \"1\"))\n}\n\n// No new mutex. Drop publishes only if an actual mapping attempt marked\n// the working record dirty, before the original guard unlocks PHYSICAL.\nstruct PhysicalGuard(MutexGuard<'static, Physical>);\nimpl std::ops::Deref for PhysicalGuard {\n    type Target = Physical;\n    fn deref(&self) -> &Physical { &self.0 }\n}\nimpl std::ops::DerefMut for PhysicalGuard {\n    fn deref_mut(&mut self) -> &mut Physical { &mut self.0 }\n}\nimpl Drop for PhysicalGuard {\n    fn drop(&mut self) {\n        let unique = self.0.shown.len();\n        self.0.mapping_observation.finish(unique, std::thread::panicking(), &MAPPING_PUBLICATION);\n    }\n}\nfn physical() -> PhysicalGuard {\n    PhysicalGuard(PHYSICAL.lock().unwrap_or_else(|e| e.into_inner()))\n}\n\n#[allow(dead_code)]\nfn mapping_diagnostic_snapshot() -> Result<mapping_diagnostic::Snapshot,mapping_diagnostic::Unavailable> {\n    if !mapping_diagnostic_on() { return Err(mapping_diagnostic::Unavailable::Disabled); }\n    MAPPING_PUBLICATION.sample()\n}", 1),
    ("    let exact = exact_placeholders_on() && physical.exact_placeholders.take(base, len);", "    physical.mapping_observation.begin();\n    let exact = exact_placeholders_on() && physical.exact_placeholders.take(base, len);", 1),
    ("        view = replace();", "        view = replace();\n        if !view.Value.is_null() && view.Value as usize != base { physical.mapping_observation.unknown(); }", 2),
    ("        unsafe { UnmapViewOfFile2(GetCurrentProcess(), view, MEM_PRESERVE_PLACEHOLDER) };", "        let rolled_back = unsafe { UnmapViewOfFile2(GetCurrentProcess(), view, MEM_PRESERVE_PLACEHOLDER) } != 0;\n        if !rolled_back { physical.mapping_observation.unknown(); }", 1),
    ("    physical.views.insert(base, (len, slice));", "    let replaced = physical.views.insert(base, (len, slice)).is_some();\n    physical.mapping_observation.inserted(len, replaced);", 1),
    ("        let unmapped = host_unmap(at);", "        physical.mapping_observation.begin();\n        let unmapped = host_unmap(at);", 1),
    ("        physical.views.remove(&at);", "        let removed = physical.views.remove(&at).is_some();\n        physical.mapping_observation.removed(size, removed);", 1),
    ("    #[test]\n    fn physical_pages_map_alias_and_unmap() {", "    // Separate process per explicit mode: global PHYSICAL starts empty.\n    #[test]\n    #[ignore = \"isolated mapping diagnostic mode\"]\n    fn mapping_diagnostic_actual_views() {\n        use mapping_diagnostic::Unavailable;\n        let mode = std::env::var(\"VICTORY_MAPPING_DIAGNOSTIC\").expect(\"explicit diagnostic mode\");\n        assert!(matches!(mode.as_str(), \"0\" | \"1\"));\n        let enabled = mode == \"1\";\n        assert_eq!(mapping_diagnostic_on(), enabled);\n        let check = |bytes: usize, unique: usize| {\n            let sample = mapping_diagnostic_snapshot();\n            if enabled {\n                let s = sample.expect(\"coherent completed mapping\");\n                assert_eq!(s.view_bytes, bytes as u64);\n                assert_eq!(s.unique_pages, unique as u64);\n                assert_eq!(s.alias_bytes, (bytes - unique * PAGE) as u64);\n            } else {\n                assert_eq!(sample, Err(Unavailable::Disabled));\n            }\n        };\n        assert_eq!(mapping_diagnostic_snapshot(), Err(if enabled { Unavailable::Initial } else { Unavailable::Disabled }));\n        let pages = allocate(2);\n        let reserve = || XMemVirtualAlloc(std::ptr::null_mut(),2*PAGE,MEM_RESERVE | PAGES_64K,0,PAGE_READWRITE);\n        let (a,b)=(reserve(),reserve());\n        assert!(!a.is_null() && !b.is_null());\n        assert_eq!(XMemMapPhysicalPages(a,2,pages.as_ptr()),a);\n        check(2*PAGE,2);\n        let second = a.wrapping_byte_add(PAGE);\n        assert!(map_alias(b as u64,second as u64,PAGE as u64));\n        check(3*PAGE,2);\n        unsafe { second.cast::<u8>().write(42); assert_eq!(b.cast::<u8>().read(),42); }\n        {\n            let mut physical=physical();\n            let _changing=victory_gpu::title_memory_remapping();\n            assert!(!unmap_with(&mut physical,b as usize,PAGE,|_| false));\n        }\n        check(3*PAGE,2);\n        assert_eq!(XMemFreePhysicalPages(2,pages.as_ptr()),1);\n        check(3*PAGE,2);\n        assert_eq!(XMemMapPhysicalPages(a,1,std::ptr::null()),a);\n        check(2*PAGE,1);\n        assert_eq!(XMemMapPhysicalPages(second,1,std::ptr::null()),second);\n        check(PAGE,1);\n        assert_eq!(unsafe { b.cast::<u8>().read() },42);\n        assert!(map_alias(b as u64,0,PAGE as u64));\n        check(0,0);\n        // Test sticky unknown publication explicitly; not an OS failure injection.\n        { physical().mapping_observation.unknown(); }\n        if enabled { assert_eq!(mapping_diagnostic_snapshot(),Err(Unavailable::Invalid)); }\n        let again=allocate(1);\n        assert_eq!(XMemMapPhysicalPages(a,1,again.as_ptr()),a);\n        assert_eq!(mapping_diagnostic_snapshot(),Err(if enabled { Unavailable::Invalid } else { Unavailable::Disabled }));\n        assert_eq!(XMemMapPhysicalPages(a,1,std::ptr::null()),a);\n        assert_eq!(XMemFreePhysicalPages(1,again.as_ptr()),1);\n    }\n\n    #[test]\n    fn physical_pages_map_alias_and_unmap() {", 1),
)

def transform(source):
    for old, new, count in REPLACEMENTS:
        if source.count(old) != count:
            raise ValueError("Unexpected mapping diagnostic anchor: " + old[:80])
        source = source.replace(old, new, count)
    return source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    path = args.checkout / PATH
    module = path.with_name("xmem_mapping_diagnostic.rs")
    try:
        if module.exists():
            raise ValueError("Mapping diagnostic module already installed")
        source = transform(path.read_text(encoding="utf-8"))
        helper = (Path(__file__).resolve().parents[1] / "probes" / "mapping_diagnostic.rs").read_text(encoding="utf-8")
        path.write_text(source, encoding="utf-8")
        module.write_text(helper, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Mapping diagnostic preparation failed: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
