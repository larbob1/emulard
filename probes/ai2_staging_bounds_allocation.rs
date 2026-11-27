// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to the approved candidate prepared texture source in scratch.
#[cfg(all(test, feature = "diagnostics"))]
mod ai2_staging_bounds_allocation {
    use super::*;
    use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering::Relaxed};
    use victory_formats::texture::{Desc, Dimension, Layout, Swizzle};
    use windows::Win32::Graphics::Dxgi::Common::{DXGI_FORMAT_R8_UNORM, DXGI_SAMPLE_DESC};
    use windows_sys::Win32::System::Memory::{VirtualAlloc, VirtualFree, MEM_RESERVE, MEM_RELEASE, PAGE_NOACCESS};

    fn r8(h: &crate::host::Host, width: u32, height: u32) ->
        (Layout, Vec<D3D12_PLACED_SUBRESOURCE_FOOTPRINT>, Vec<u32>, Vec<u64>, u64) {
        let layout = Layout::new(&Desc { dimension: Dimension::Tex2d,
            width, height, depth: 1, mips: 1, element_bytes: 1, block: 1,
            samples: 1, swizzle: Swizzle::LINEAR }).unwrap();
        let d = D3D12_RESOURCE_DESC {
            Dimension: D3D12_RESOURCE_DIMENSION_TEXTURE2D, Width: u64::from(width),
            Height: height, DepthOrArraySize: 1, MipLevels: 1, Format: DXGI_FORMAT_R8_UNORM,
            SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
            Layout: D3D12_TEXTURE_LAYOUT_UNKNOWN, ..Default::default()
        };
        let mut footprints = vec![D3D12_PLACED_SUBRESOURCE_FOOTPRINT::default()];
        let mut rows = vec![0u32];
        let mut active = vec![0u64];
        let mut total = 0;
        unsafe {
            h.device.GetCopyableFootprints(&d, 0, 1, 0, Some(footprints.as_mut_ptr()),
                Some(rows.as_mut_ptr()), Some(active.as_mut_ptr()), Some(&mut total));
        }
        assert_eq!(active, vec![u64::from(width)]);
        assert_eq!(rows, vec![height]);
        (layout, footprints, rows, active, total)
    }

    struct Reservation(*mut core::ffi::c_void);
    impl Drop for Reservation {
        fn drop(&mut self) {
            let freed = unsafe { VirtualFree(self.0, 0, MEM_RELEASE) };
            if !std::thread::panicking() { assert_ne!(freed, 0); }
        }
    }

    #[test]
    fn actual_staging_bounds_pool_and_zero_fill() {
        let expected = std::env::var("AI2_EXPECT_POOL").expect("explicit pool mode");
        assert!(expected == "0" || expected == "1");
        let pool = expected == "1";
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(), Ok("1"));
        assert_eq!(std::env::var("VICTORY_STAGING_POOL").as_deref(), Ok(expected.as_str()));
        assert_eq!(staging_pool(), pool);
        assert!(crate::host::warp_adapter().is_ok());
        let h = host().expect("software host");
        let (layout, footprints, rows, active, total) = r8(h, 4, 2);
        let required = staging_extent(total, &footprints, &rows, &active, &layout, 1).unwrap();
        assert_eq!((total, required), (260, 512));
        assert_eq!(staging_extent(total - 1, &footprints, &rows, &active, &layout, 1), None);
        assert_eq!(staging_extent(total, &footprints, &rows, &active, &layout, 0), None);
        assert_eq!(staging_extent(total, &footprints, &[], &active, &layout, 1), None);
        let mut bad = footprints.clone();
        bad[0].Footprint.RowPitch = 1;
        assert_eq!(staging_extent(total, &bad, &rows, &active, &layout, 1), None);
        assert!(staging_buffer(h, 0).is_none());
        assert!(staging_buffer(h, u64::MAX).is_none());

        let (buffer, data, pooled) = staging_buffer(h, required).expect("actual allocation");
        let width = unsafe { buffer.GetDesc().Width };
        assert_eq!(pooled, if pool { 65536 } else { 0 });
        assert_eq!(width, if pool { 65536 } else { required });
        assert!(staging_mapping_fits(&buffer, data, required, width));
        assert!(!staging_mapping_fits(&buffer, data, width + 1, width));
        assert!(!staging_mapping_fits(&buffer, std::ptr::null_mut(), required, width));
        assert!(unsafe { std::slice::from_raw_parts(data, required as usize) }.iter().all(|&b| b == 0));
        // Owned unmapped title-like address is queried only for on-demand
        // level presence; actual detile input is independently owned Vec.
        let reserve = Reservation(unsafe { VirtualAlloc(std::ptr::null(), 65536, MEM_RESERVE, PAGE_NOACCESS) });
        assert!(!reserve.0.is_null());
        assert!(!committed(reserve.0.cast(), layout.size as usize));
        let src = vec![0x5a; layout.size as usize];
        let old_count = STAGED[0].load(Relaxed);
        let old_bytes = STAGED[1].load(Relaxed);
        STAGED[0].fetch_add(1, Relaxed);
        STAGED[1].fetch_add(total, Relaxed);
        let staging = Staging {
            buffer, size: required, data, footprints, rows, layout,
            mips: 1, bytes: total, memory: reserve.0.cast(), last: Mutex::default(),
            dirty: AtomicBool::new(false), uploaded: AtomicBool::new(false),
            used: AtomicU64::new(0), on_demand: true, detiled: AtomicU32::new(0),
            judged: [const { AtomicU64::new(0) }; 2], waiting: AtomicU64::new(0), pooled,
        };
        // Entire width was checked above. Fill a sentinel over the full
        // owned allocation; on-demand zeroing must clear exactly required.
        unsafe { std::ptr::write_bytes(data, 0xa5, width as usize); }
        staging.detile(&src);
        assert_eq!(staging.detiled.load(Relaxed), 0);
        let contents = unsafe { std::slice::from_raw_parts(data, width as usize) };
        assert!(contents[..required as usize].iter().all(|&b| b == 0));
        assert!(contents[required as usize..].iter().all(|&b| b == 0xa5));
        // Seed all required bytes again, then return through actual Drop.
        unsafe { std::ptr::write_bytes(data, 0xa5, required as usize); }
        let prior = data as usize;
        drop(staging);
        assert_eq!(STAGED[0].load(Relaxed), old_count);
        assert_eq!(STAGED[1].load(Relaxed), old_bytes);
        let (buffer, data, pooled2) = staging_buffer(h, required).expect("second allocation");
        assert_eq!(pooled2, pooled);
        assert!(staging_mapping_fits(&buffer, data, required, width));
        if pool {
            assert_eq!(data as usize, prior, "actual spare reuse");
        }
        let contents = unsafe { std::slice::from_raw_parts(data, width as usize) };
        assert!(contents[..required as usize].iter().all(|&b| b == 0));
        if pool {
            assert!(contents[required as usize..].iter().all(|&b| b == 0xa5));
        }
        drop(buffer); // no remaining reference or GPU use; this one is not returned
        drop(reserve);
        eprintln!("staging_bounds small pool={} logical={total} required={required} width={width} reused={pool}", u8::from(pool));

        // Exact 64KiB/8MiB class boundaries and real >8MiB unpooled route.
        // One allocation at a time; no large synthetic title data or GPU work.
        for (w, hgt, want) in [(4, 256, 65536u64), (1001,8192,8u64<<20),
                              (1001,8193,(8u64<<20)+1024)] {
            let (layout, fp, rows, active, total) = r8(h, w, hgt);
            let need = staging_extent(total, &fp, &rows, &active, &layout, 1).unwrap();
            assert_eq!(need, want);
            let (buffer, data, class) = staging_buffer(h, need).expect("bounded allocation");
            let actual = unsafe { buffer.GetDesc().Width };
            let expected_class = if pool && need <= 8<<20 { need } else { 0 };
            assert_eq!(class, expected_class);
            assert_eq!(actual, need);
            assert!(staging_mapping_fits(&buffer, data, need, actual));
            assert!(unsafe { std::slice::from_raw_parts(data, need as usize) }.iter().all(|&b| b == 0));
            eprintln!("staging_bounds boundary pool={} logical={total} required={need} width={actual} class={class}", u8::from(pool));
            drop(buffer);
        }
    }
}
