// SPDX-License-Identifier: GPL-3.0-or-later
//! Native synthetic test only; no production read path changes.
use super::*;
use windows_sys::Win32::System::Memory::{FILE_MAP_READ, MapViewOfFile};

const LIMIT: usize = 8 * 1024 * 1024;

// A pinned plan retains backing identity, not a snapshot of contents.
// This test owns committed memory and does not write concurrently.
fn read_plan(plan: &[pinned_views::PinnedSpan<Section>], out: &mut [u8]) -> bool {
    if out.len() > LIMIT { return false; }
    let Some(total) = plan.iter().try_fold(0usize, |n, s| n.checked_add(s.len)) else { return false; };
    if total != out.len() { return false; }
    let mut result = Vec::with_capacity(total);
    for span in plan {
        let aligned = span.offset / PAGE * PAGE;
        let within = span.offset - aligned;
        let Some(len) = within.checked_add(span.len) else { return false; };
        if span.len == 0 || span.offset.checked_add(span.len).is_none() { return false; }
        let offset = aligned as u64;
        // SAFETY: fixture-owned committed section; Arc retains its handle.
        let at = unsafe { MapViewOfFile(span.section.0, FILE_MAP_READ, (offset >> 32) as u32, offset as u32, len) };
        if at.Value.is_null() { return false; }
        let view = View { at, len };
        // SAFETY: fixture committed this range, owns the view, and does
        // not write through aliases during the copy.
        let bytes = unsafe { std::slice::from_raw_parts(view.at.Value.cast::<u8>().add(within), span.len) };
        result.extend_from_slice(bytes);
        drop(view);
    }
    out.copy_from_slice(&result);
    true
}

fn reserve(n: usize) -> *mut c_void {
    let at = XMemVirtualAlloc(std::ptr::null_mut(), n * PAGE,
        MEM_RESERVE | PAGES_64K, 0, PAGE_READWRITE);
    assert!(!at.is_null());
    at
}

#[test]
fn pinned_backing_reads_survive_alias_replacement_and_retirement() {
    assert!(mirror_enabled(), "run with VICTORY_MAP_PINNED_MIRROR=1");
    let mut pages = [0usize; 3];
    let mut n = pages.len();
    assert_eq!(XMemAllocatePhysicalPages(0, &mut n, pages.as_mut_ptr()), 1);
    assert_eq!(n, 3);
    let pool = reserve(3);
    let dest = reserve(2);
    assert_eq!(XMemMapPhysicalPages(pool, n, pages.as_ptr()), pool);
    {
        let mut stable = page_window(&pages, 0, n * PAGE).unwrap();
        for (i, bytes) in stable.bytes().chunks_exact_mut(PAGE).enumerate() {
            bytes.fill((i + 1) as u8);
        }
    }
    assert!(map_alias(dest as u64, pool.wrapping_byte_add(2 * PAGE) as u64, PAGE as u64));
    assert!(map_alias(dest.wrapping_byte_add(PAGE) as u64, pool as u64, PAGE as u64));
    let address = dest as usize + PAGE - 3;
    let plan = {
        let physical = physical();
        assert!(!physical.mirror_failed);
        physical.pinned_mirror.resolve(address, 8).unwrap()
    };
    assert_eq!(plan.len(), 2);
    assert_eq!(plan[0].offset, 3 * PAGE - 3);
    assert_eq!(plan[1].offset, 0);
    let weak = Arc::downgrade(&plan[0].section);
    let mut bytes = [0; 8];
    assert!(read_plan(&plan, &mut bytes));
    assert_eq!(bytes, [3,3,3,1,1,1,1,1]);
    assert_eq!(bytes.as_slice(), unsafe { std::slice::from_raw_parts(address as *const u8, 8) });
    // Replacing an alias must not redirect an earlier plan.
    assert!(map_alias(dest as u64, pool.wrapping_byte_add(PAGE) as u64, PAGE as u64));
    let newer = {
        let physical = physical();
        assert!(!physical.mirror_failed);
        physical.pinned_mirror.resolve(address, 8).unwrap()
    };
    assert!(read_plan(&newer, &mut bytes));
    assert_eq!(bytes, [2,2,2,1,1,1,1,1]);
    assert!(read_plan(&plan, &mut bytes));
    assert_eq!(bytes, [3,3,3,1,1,1,1,1]);
    drop(newer);
    assert!(map_alias(dest as u64, 0, (2 * PAGE) as u64));
    assert!(map_alias(pool as u64, 0, (3 * PAGE) as u64));
    assert_eq!(XMemFreePhysicalPages(n, pages.as_ptr()), 1);
    {
        let physical = physical();
        assert!(!physical.mirror_failed);
        assert!(physical.pinned_mirror.resolve(address, 8).is_none());
    }
    assert!(weak.upgrade().is_some());
    assert!(read_plan(&plan, &mut bytes));
    assert_eq!(bytes, [3,3,3,1,1,1,1,1]);
    let mut wrong = [42; 7];
    assert!(!read_plan(&plan, &mut wrong));
    assert_eq!(wrong, [42; 7]);
    drop(plan);
    assert!(weak.upgrade().is_none(), "unexpected section lifetime retention");
}
