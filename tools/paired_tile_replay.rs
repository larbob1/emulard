// SPDX-License-Identifier: GPL-3.0-or-later

use super::*;
use super::software_pages::{PageTable, SectionKey};
const POOL_KEY: SectionKey = SectionKey { id: 1, generation: 1 };

#[derive(Clone, Copy)]
struct Mapping {
    destination: usize,
    source: Option<usize>,
}

fn reserve(pages: usize) -> *mut c_void {
    let at = XMemVirtualAlloc(
        std::ptr::null_mut(),
        pages * PAGE,
        MEM_RESERVE | PAGES_64K,
        0,
        PAGE_READWRITE,
    );
    assert!(!at.is_null());
    at
}

fn resolve(table: &[Option<usize>], backing: &[u8], address: usize, out: &mut [u8]) -> bool {
    let mut done = 0;
    while done < out.len() {
        let at = address + done;
        let Some(Some(page)) = table.get(at / PAGE) else {
            return false;
        };
        let within = at % PAGE;
        let count = (PAGE - within).min(out.len() - done);
        let source = page * PAGE + within;
        out[done..done + count].copy_from_slice(&backing[source..source + count]);
        done += count;
    }
    true
}

fn resolve_both(table: &[Option<usize>], model: &PageTable, backing: &[u8], address: usize, out: &mut [u8]) -> bool {
    let ok = resolve(table, backing, address, out);
    let mut actual = vec![0; out.len()];
    let result = model.read(address, &mut actual, |key| (key == POOL_KEY).then_some(backing));
    assert_eq!(result.is_ok(), ok, "software page resolution differs");
    if ok { assert_eq!(actual, out, "software page bytes differ"); }
    ok
}

fn check_texture(table: &[Option<usize>], model: &PageTable, backing: &[u8], destination: *const c_void) {
    use victory_formats::texture::{Desc, Dimension, Layout, Swizzle};

    let layout = Layout::new(&Desc {
        dimension: Dimension::Tex2d,
        width: 256,
        height: 256,
        depth: 1,
        mips: 1,
        element_bytes: 4,
        block: 1,
        samples: 1,
        swizzle: Swizzle::SW_64KB_D,
    })
    .unwrap();
    let mut tiled = vec![0; layout.size as usize];
    assert!(resolve_both(table, model, backing, 0, &mut tiled));
    // SAFETY: the fixture mapped all four destination pages and the
    // table read above verified the requested range fits in them.
    let native = unsafe { std::slice::from_raw_parts(destination.cast::<u8>(), tiled.len()) };
    let pitch = 256 * 4;
    let bytes = pitch * 256;
    let mut expected = vec![0; bytes];
    let mut actual = vec![0; bytes];
    layout
        .detile(native, 0, 0, &mut expected, pitch, bytes)
        .unwrap();
    layout
        .detile(&tiled, 0, 0, &mut actual, pitch, bytes)
        .unwrap();
    assert_eq!(actual, expected, "detiled texture differs");
}

fn replay(pool_pages: usize, slots: usize, operations: &[Mapping], exhaustive: bool) {
    let (mut pages, mut count) = (vec![0; pool_pages], pool_pages);
    assert_eq!(
        XMemAllocatePhysicalPages(0, &mut count, pages.as_mut_ptr()),
        1
    );
    assert_eq!(count, pool_pages);
    let pool = reserve(pool_pages);
    let destination = reserve(slots);
    assert_eq!(XMemMapPhysicalPages(pool, pool_pages, pages.as_ptr()), pool);
    let mut stable =
        page_window(&pages, 0, pool_pages * PAGE).expect("stable view of backing pages");
    for (index, bytes) in stable.bytes().chunks_exact_mut(PAGE).enumerate() {
        bytes.fill((index % 251) as u8);
        bytes[..4].copy_from_slice(&(index as u32).to_le_bytes());
    }

    assert!(operations.iter().all(|op| op.destination < slots && op.source.is_none_or(|p| p < pool_pages)));
    let mut table = vec![None; slots];
    let mut model = PageTable::default();
    assert_eq!(super::software_pages::PAGE_BYTES, PAGE);
    let mut readback = vec![0; PAGE];
    for (index, mapping) in operations.iter().enumerate() {
        let start = mapping.destination * PAGE;
        let at = destination.wrapping_byte_add(start);
        let from = mapping
            .source
            .map_or(0, |s| pool.wrapping_byte_add(s * PAGE) as u64);
        assert!(map_alias(at as u64, from, PAGE as u64), "operation {index}");
        table[mapping.destination] = mapping.source;
        if let Some(source) = mapping.source {
            model.map(mapping.destination, 1, POOL_KEY, source).unwrap();
        } else {
            model.unmap(mapping.destination, 1).unwrap();
        }
        if let Some(source) = mapping.source {
            // Mutate the backing through the stable view after the alias is mapped.
            // A software table pointing at a stale copy fails the full-page comparison.
            stable.bytes()[source * PAGE + PAGE - 1] = (index % 251) as u8;
            // SAFETY: the mapper successfully created this PAGE-byte view.
            let expected = unsafe { std::slice::from_raw_parts(at.cast::<u8>(), PAGE) };
            assert!(resolve_both(&table, &model, stable.bytes(), start, &mut readback));
            assert_eq!(readback, expected, "operation {index}");
        } else {
            let mut info = std::mem::MaybeUninit::<MEMORY_BASIC_INFORMATION>::uninit();
            // SAFETY: output points to storage for a complete record.
            assert_ne!(
                unsafe {
                    VirtualQueryEx(
                        GetCurrentProcess(),
                        at,
                        info.as_mut_ptr(),
                        size_of::<MEMORY_BASIC_INFORMATION>(),
                    )
                },
                0
            );
            assert_eq!(
                unsafe { info.assume_init() }.State,
                MEM_RESERVE,
                "operation {index}"
            );
            assert!(!resolve_both(&table, &model, stable.bytes(), start, &mut [0]));
        }
        if exhaustive {
            for (slot, physical) in table.iter().enumerate() {
                if physical.is_some() {
                    let addr = destination.wrapping_byte_add(slot * PAGE);
                    // SAFETY: this slot remains mapped from an earlier operation.
                    let expected = unsafe { std::slice::from_raw_parts(addr.cast::<u8>(), PAGE) };
                    assert!(resolve_both(&table, &model, stable.bytes(), slot * PAGE, &mut readback));
                    assert_eq!(readback, expected, "operation {index}, slot {slot}");
                }
                if physical.is_some() && table.get(slot + 1).is_some_and(Option::is_some) {
                    let at = (slot + 1) * PAGE - 13;
                    let mut crossing = [0; 53];
                    assert!(resolve_both(&table, &model, stable.bytes(), at, &mut crossing));
                    // SAFETY: the two adjacent slots are both mapped.
                    let expected = unsafe {
                        std::slice::from_raw_parts(
                            destination.wrapping_byte_add(at).cast::<u8>(),
                            crossing.len(),
                        )
                    };
                    assert_eq!(crossing, expected, "operation {index}, page boundary");
                }
            }
        }
    }

    if exhaustive {
        check_texture(&table, &model, stable.bytes(), destination);
    }

    drop(stable);
    assert!(map_alias(destination as u64, 0, (slots * PAGE) as u64));
    assert!(map_alias(pool as u64, 0, (pool_pages * PAGE) as u64));
    assert_eq!(XMemFreePhysicalPages(pool_pages, pages.as_ptr()), 1);
}

#[test]
fn tile_replay_checks_remaps_aliases_and_cross_page_reads() {
    let operations = [
        (0, Some(0)),
        (1, Some(0)),
        (2, Some(1)),
        (1, None),
        (1, Some(2)),
        (0, Some(2)),
        (2, None),
        (3, Some(0)),
        (2, Some(0)),
    ]
    .map(|(destination, source)| Mapping {
        destination,
        source,
    });
    replay(3, 4, &operations, true);
}

#[test]
#[ignore = "requires a normalized capture from the title"]
fn tile_replay_captured_ranges() {
    let trace = std::env::var_os("VICTORY_TILE_REPLAY").expect("set VICTORY_TILE_REPLAY");
    let data = std::fs::read_to_string(trace).expect("read normalized replay");
    let mut lines = data.lines();
    let header: Vec<usize> = lines
        .next()
        .unwrap()
        .split(',')
        .map(|n| n.parse().unwrap())
        .collect();
    assert_eq!(header.len(), 2);
    assert!(header.iter().all(|&n| (1..=4096).contains(&n)), "replay fixture memory limit");
    let operations: Vec<_> = lines
        .map(|line| {
            let (index, source) = line.split_once(',').expect("destination,source");
            Mapping {
                destination: index.parse().unwrap(),
                source: if source == "-" {
                    None
                } else {
                    Some(source.parse().unwrap())
                },
            }
        })
        .collect();
    assert!(!operations.is_empty());
    replay(header[0], header[1], &operations, false);
    println!(
        "verified {} mapping operations in {} destination pages",
        operations.len(),
        header[1]
    );
}
