// SPDX-License-Identifier: GPL-3.0-or-later
// Descriptor-only native review: append to the exact prepared GPU texture module.
// No mapping, allocation of texture storage, slice construction, or queue execution.
#[cfg(all(test, feature = "diagnostics"))]
mod ai2_footprint_bounds_review {
    use super::*;
    use windows::Win32::Graphics::Direct3D::D3D_FEATURE_LEVEL_12_0;
    use windows::Win32::Graphics::Dxgi::Common::{
        DXGI_FORMAT, DXGI_FORMAT_BC1_UNORM, DXGI_FORMAT_R8_UNORM,
        DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_SAMPLE_DESC,
    };

    fn device() -> ID3D12Device {
        let adapter = crate::host::warp_adapter().expect("WARP required");
        let mut device: Option<ID3D12Device> = None;
        unsafe {
            D3D12CreateDevice(&adapter, D3D_FEATURE_LEVEL_12_0, &mut device)
                .expect("independent software device");
        }
        device.expect("device")
    }

    fn descriptor(dim: D3D12_RESOURCE_DIMENSION, width: u64, height: u32,
                  depth_or_array: u16, mips: u16, format: DXGI_FORMAT)
                  -> D3D12_RESOURCE_DESC {
        D3D12_RESOURCE_DESC {
            Dimension: dim, Width: width, Height: height,
            DepthOrArraySize: depth_or_array, MipLevels: mips, Format: format,
            SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
            Layout: D3D12_TEXTURE_LAYOUT_UNKNOWN, ..Default::default()
        }
    }

    // Expected active row size/rows/depth are independently enumerated
    // for the small uncompressed and BC1 descriptors below.
    fn inspect(device: &ID3D12Device, name: &str, desc: D3D12_RESOURCE_DESC,
               expected: &[(u64, u32, u32)]) -> (u64, u64) {
        let n = expected.len();
        let mut layouts = vec![D3D12_PLACED_SUBRESOURCE_FOOTPRINT::default(); n];
        let mut rows = vec![0u32; n];
        let mut row_sizes = vec![0u64; n];
        let mut total = 0u64;
        unsafe {
            device.GetCopyableFootprints(&desc, 0, n as u32, 0,
                Some(layouts.as_mut_ptr()), Some(rows.as_mut_ptr()),
                Some(row_sizes.as_mut_ptr()), Some(&mut total));
        }
        assert!(total != u64::MAX && total != 0, "{name}: valid total");
        let mut active_max = 0u64;
        let mut full_max = 0u64;
        for i in 0..n {
            let f = layouts[i].Footprint;
            let offset = layouts[i].Offset;
            let (active, row_count, depth) = expected[i];
            assert_eq!((row_sizes[i], rows[i], f.Depth), (active, row_count, depth),
                "{name} subresource {i}");
            assert_eq!(offset % 512, 0, "{name}: placement alignment");
            let pitch = u64::from(f.RowPitch);
            assert!(pitch >= active && pitch % 256 == 0);
            let count = u64::from(row_count).checked_mul(u64::from(depth)).unwrap();
            assert!(count != 0);
            let full = offset.checked_add(pitch.checked_mul(count).unwrap()).unwrap();
            let end = offset.checked_add(pitch.checked_mul(count - 1).unwrap())
                .and_then(|v| v.checked_add(active)).unwrap();
            assert!(offset >= active_max, "{name}: active subresources overlap");
            assert!(end <= total && end <= full, "{name}: required extent");
            active_max = active_max.max(end);
            full_max = full_max.max(full);
            eprintln!("footprint {name} sub={i} offset={offset} pitch={pitch} rows={row_count} depth={depth} active_row={active} active_end={end} full_end={full} total={total}");
        }
        // Reference helper excludes padding following the last active row.
        // A native implementation returning a different total is a
        // meaningful contrary receipt, not silently treated as a pass.
        assert_eq!(total, active_max, "{name}: final active extent");
        let unpooled_excess = full_max.saturating_sub(total);
        // The small-buffer pool rounds allocation up; distinguish logical
        // footprint size from its backing resource's declared width.
        let pooled_width = total.max(64 << 10).checked_next_power_of_two().unwrap();
        assert!(full_max <= pooled_width, "{name}: small rounded allocation");
        eprintln!("footprint_summary {name} total={total} full_end={full_max} unpooled_excess={unpooled_excess} modeled_pooled_width={pooled_width}");
        (total, full_max)
    }

    #[test]
    fn actual_descriptor_final_row_extent() {
        let d = device();
        assert_eq!(inspect(&d, "r8_4x2",
            descriptor(D3D12_RESOURCE_DIMENSION_TEXTURE2D, 4, 2, 1, 1, DXGI_FORMAT_R8_UNORM),
            &[(4, 2, 1)]), (260, 512));
        assert_eq!(inspect(&d, "rgba8_aligned",
            descriptor(D3D12_RESOURCE_DIMENSION_TEXTURE2D, 64, 2, 1, 1, DXGI_FORMAT_R8G8B8A8_UNORM),
            &[(256, 2, 1)]), (512, 512));
        inspect(&d, "r8_array_mips",
            descriptor(D3D12_RESOURCE_DIMENSION_TEXTURE2D, 8, 4, 2, 3, DXGI_FORMAT_R8_UNORM),
            &[(8,4,1), (4,2,1), (2,1,1), (8,4,1), (4,2,1), (2,1,1)]);
        inspect(&d, "r8_volume",
            descriptor(D3D12_RESOURCE_DIMENSION_TEXTURE3D, 8, 4, 3, 1, DXGI_FORMAT_R8_UNORM),
            &[(8,4,3)]);
        inspect(&d, "bc1_8x8",
            descriptor(D3D12_RESOURCE_DIMENSION_TEXTURE2D, 8, 8, 1, 1, DXGI_FORMAT_BC1_UNORM),
            &[(16,2,1)]);
    }
}
