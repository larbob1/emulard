// SPDX-License-Identifier: GPL-3.0-or-later
// Append-only native review fixture. Not registered or production code.
#[cfg(all(test, feature = "diagnostics"))]
mod ai2_staging_failure_review {
    use super::*;
    use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering::Relaxed};
    use victory_formats::texture::{Desc, Dimension, Layout, Swizzle};
    use windows::Win32::Graphics::Direct3D::D3D_FEATURE_LEVEL_12_0;
    use windows::Win32::Graphics::Dxgi::Common::DXGI_SAMPLE_DESC;

    const PITCH: usize = 256;
    const ROWS: usize = 2;
    const SLICES: usize = 3;
    const ACTIVE: usize = 4;
    const STRIDE: usize = PITCH * ROWS;
    const BYTES: usize = STRIDE * SLICES;
    const GUARD: usize = 32;
    const TOTAL: usize = BYTES + 2 * GUARD;
    const SENTINEL: u8 = 0xcc;

    fn buffer() -> ID3D12Resource {
        let adapter = crate::host::warp_adapter().expect("WARP required");
        let mut device: Option<ID3D12Device> = None;
        unsafe {
            D3D12CreateDevice(&adapter, D3D_FEATURE_LEVEL_12_0, &mut device)
                .expect("independent software device");
        }
        let device = device.expect("device");
        let heap = D3D12_HEAP_PROPERTIES {
            Type: D3D12_HEAP_TYPE_UPLOAD, CreationNodeMask: 1,
            VisibleNodeMask: 1, ..Default::default()
        };
        let desc = D3D12_RESOURCE_DESC {
            Dimension: D3D12_RESOURCE_DIMENSION_BUFFER, Width: TOTAL as u64,
            Height: 1, DepthOrArraySize: 1, MipLevels: 1,
            SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
            Layout: D3D12_TEXTURE_LAYOUT_ROW_MAJOR, ..Default::default()
        };
        let mut result: Option<ID3D12Resource> = None;
        unsafe {
            device.CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE,
                &desc, D3D12_RESOURCE_STATE_GENERIC_READ, None, &mut result)
                .expect("owned upload resource");
        }
        result.expect("buffer")
    }

    // For this specific linear 4x2x3 descriptor, each slice has two
    // 256-byte rows. Construct bytes independently of Layout::offset.
    fn source(value: u8) -> Vec<u8> {
        let mut data = vec![0x7d; BYTES];
        for slice in 0..SLICES {
            for row in 0..ROWS {
                for col in 0..ACTIVE {
                    data[slice * STRIDE + row * PITCH + col] =
                        if value == 0 { 0 } else { value + (slice * 8 + row * 4 + col) as u8 };
                }
            }
        }
        data
    }

    fn expect_bytes(old: &[u8], new: &[u8], changed_prefix: usize) -> Vec<u8> {
        let mut expected = vec![SENTINEL; TOTAL];
        for slice in 0..SLICES {
            let src = if slice < changed_prefix { new } else { old };
            for row in 0..ROWS {
                let at = slice * STRIDE + row * PITCH;
                expected[GUARD + at..GUARD + at + ACTIVE]
                    .copy_from_slice(&src[at..at + ACTIVE]);
            }
        }
        expected
    }

    fn check(fail_at: Option<usize>, zero: bool) {
        let old = source(0x10);
        let new = source(if zero { 0 } else { 0x50 });
        let layout = Layout::new(&Desc {
            dimension: Dimension::Tex2d, width: ACTIVE as u32,
            height: ROWS as u32, depth: SLICES as u32, mips: 1,
            element_bytes: 1, block: 1, samples: 1, swizzle: Swizzle::LINEAR,
        }).expect("linear layout");
        assert_eq!(layout.size as usize, BYTES);
        assert_eq!(layout.slice_size as usize, STRIDE);
        let footprints = (0..SLICES).map(|i| D3D12_PLACED_SUBRESOURCE_FOOTPRINT {
            Offset: (i * STRIDE) as u64,
            Footprint: D3D12_SUBRESOURCE_FOOTPRINT {
                Width: ACTIVE as u32, Height: ROWS as u32,
                Depth: 1, RowPitch: PITCH as u32, ..Default::default()
            },
        }).collect::<Vec<_>>();
        let buffer = buffer();
        let mut raw = std::ptr::null_mut();
        // No queue, registry, title mapping, or GPU access. Allocate the
        // ENTIRE footprint span plus guards even for the malformed pitch.
        // The fixture uses a shifted pointer; never record a GPU upload.
        unsafe {
            buffer.Map(0, None, Some(&mut raw)).expect("owned mapping");
            assert!(!raw.is_null());
            raw.cast::<u8>().write_bytes(SENTINEL, TOTAL);
        }
        let base = raw.cast::<u8>();
        let rows = vec![ROWS as u32; SLICES];
        let mut staging = Staging {
            buffer: buffer.clone(), size: BYTES as u64,
            data: unsafe { base.add(GUARD) }, footprints, rows, layout,
            mips: 1, bytes: BYTES as u64, memory: old.as_ptr(),
            last: Mutex::default(), dirty: AtomicBool::new(false),
            uploaded: AtomicBool::new(false), used: AtomicU64::new(0),
            on_demand: false, detiled: AtomicU32::new(0),
            judged: [const { AtomicU64::new(0) }; 2],
            waiting: AtomicU64::new(0), pooled: 0,
        };
        // Balance the real Drop accounting; no spare-pool insertion.
        STAGED[0].fetch_add(1, Relaxed);
        STAGED[1].fetch_add(BYTES as u64, Relaxed);

        // Seed real staging contents, then emulate the prior valid state.
        staging.detile(&old);
        assert_eq!(unsafe { std::slice::from_raw_parts(base, TOTAL) },
                   expect_bytes(&old, &old, 0).as_slice());
        staging.dirty.store(false, Relaxed);
        staging.uploaded.store(true, Relaxed);
        if let Some(i) = fail_at {
            // Real Layout::detile rejects row pitch < active row width
            // BEFORE writing this subresource. Its supplied slice still
            // lies completely inside the independently owned allocation.
            staging.footprints[i].Footprint.RowPitch = 1;
        }
        staging.detile(&new);
        let changed = fail_at.unwrap_or(SLICES);
        assert_eq!(unsafe { std::slice::from_raw_parts(base, TOTAL) },
                   expect_bytes(&old, &new, changed).as_slice(),
                   "exact bytes, untouched suffix, row padding and guards");
        // This is a reproduction of the CURRENT behavior, not a desired
        // transactional contract: dirty becomes true even on refusal.
        assert!(staging.dirty.load(Relaxed));
        assert!(staging.uploaded.load(Relaxed));
        drop(staging);
        unsafe { buffer.Unmap(0, None); }
    }

    #[test]
    fn actual_partial_detile_publication_reproduction() {
        for i in 0..SLICES {
            check(Some(i), false);
        }
    }

    #[test]
    fn actual_complete_detile_including_mapped_zero() {
        check(None, false);
        check(None, true);
    }
}
