// SPDX-License-Identifier: GPL-3.0-or-later
#[cfg(all(test, feature = "diagnostics"))]
mod ai1_shadow_handback_receipt {
    use super::*;
    use windows::core::Interface;
    use windows_sys::Win32::System::Memory::{
        VirtualAlloc, VirtualFree, MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, PAGE_READWRITE,
    };
    const A: u64 = 0x1_0001_0000;
    const N: usize = 2 * 65536;
    const MARK: u64 = 0x1122334455667788;

    fn buffer(device: &ID3D12Device, kind: D3D12_HEAP_TYPE,
              state: D3D12_RESOURCE_STATES, size: u64) -> ID3D12Resource {
        let heap = D3D12_HEAP_PROPERTIES {
            Type: kind, CreationNodeMask: 1, VisibleNodeMask: 1, ..Default::default()
        };
        let desc = D3D12_RESOURCE_DESC {
            Dimension: D3D12_RESOURCE_DIMENSION_BUFFER, Width: size,
            Height: 1, DepthOrArraySize: 1, MipLevels: 1,
            SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
            Layout: D3D12_TEXTURE_LAYOUT_ROW_MAJOR, ..Default::default()
        };
        let mut result: Option<ID3D12Resource> = None;
        unsafe {
            device.CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc,
                state, None, &mut result).expect("owned buffer");
        }
        result.expect("resource")
    }



    struct Owned(*mut core::ffi::c_void);
    impl Drop for Owned {
        fn drop(&mut self) {
            crate::shadow::unregister(A as usize, A);
            let freed = unsafe { VirtualFree(self.0, 0, MEM_RELEASE) };
            if !std::thread::panicking() { assert_ne!(freed, 0); }
        }
    }

    #[test]
    fn actual_owned_shadow_handback() {
        let mode = std::env::var("AI1_EXPECT_WIDE").expect("explicit route");
        assert!(mode == "0" || mode == "1");
        assert_eq!(crate::shadow::wide_back(), mode == "1");
        assert!(!late() && !relay() && !crate::shadow::relay() && !crate::shadow::cards());
        assert_eq!(crate::inplace::level(), 0);
        let h = host().expect("WARP host");
        let adapter = h.adapter.as_ref().expect("host adapter identity");
        let desc = unsafe { adapter.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32, 0);
        assert_eq!(STARTED.load(Ordering::Acquire), 0);
        assert_eq!(FINISHED.load(Ordering::Acquire), 0);
        assert_eq!(*h.submitted.lock().unwrap(), 0);
        assert_eq!(unsafe { h.fence.GetCompletedValue() }, 0);

        let p = unsafe { VirtualAlloc(A as *const _, N, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) };
        assert!(!p.is_null());
        if p as u64 != A {
            unsafe { VirtualFree(p, 0, MEM_RELEASE); }
            panic!("owned address mismatch");
        }
        assert!(crate::shadow::extent(A).is_none());
        crate::shadow::register(A as usize, A, N as u64);
        let owned = Owned(p);
        let initial: Vec<u8> = (0..N).map(|i| (i as u8).wrapping_mul(7) ^ 0x6d).collect();
        unsafe { std::ptr::copy_nonoverlapping(initial.as_ptr(), p.cast::<u8>(), N); }
        let copy = crate::shadow::find(A, N as u64).expect("owned registered shadow");
        assert_eq!(copy.span(), (A, N as u64));
        assert!(!copy.carded());
        let upload = buffer(&h.device, D3D12_HEAP_TYPE_UPLOAD,
                            D3D12_RESOURCE_STATE_GENERIC_READ, 64);
        let pattern: Vec<u8> = (0..64).map(|i| 0xa0u8.wrapping_add(i as u8)).collect();
        let mut mapped = std::ptr::null_mut();
        unsafe {
            upload.Map(0, Some(&D3D12_RANGE { Begin: 0, End: 0 }), Some(&mut mapped)).unwrap();
            assert!(!mapped.is_null());
            std::ptr::copy_nonoverlapping(pattern.as_ptr(), mapped.cast::<u8>(), 64);
            upload.Unmap(0, Some(&D3D12_RANGE { Begin: 0, End: 64 }));
        }
        let list = h.new_list().unwrap();
        copy.refresh(&list, A, N as u64);
        // Overlapping declarations across a 64KiB boundary and a separate
        // declared interval. Only the actual GPU changes should land.
        for (offset, len) in [(65520u64, 32u64), (65528, 48), (90000, 64)] {
            copy.gpu_writes(&list, A+offset, len);
        }
        unsafe {
            // Buffer COMMON -> COPY_DEST implicit promotion, decay after
            // synchronous execution. Both resources retained until receipt.
            list.list.CopyBufferRegion(&copy.buffer, 65528, &upload, 0, 32);
            list.list.CopyBufferRegion(&copy.buffer, 90016, &upload, 32, 32);
        }
        // If handback followed the bottom write, the GPU bytes could
        // overwrite this marker. Check all other bytes independently.
        list.defer_write(unsafe { p.cast::<u8>().add(65528) },
                         crate::queue::Written::Value(MARK), 8);
        list.close();
        assert_eq!(unsafe { std::slice::from_raw_parts(p.cast::<u8>(), N) }, initial.as_slice());
        let result = h.submit(&[&list], false);
        if result.is_some() { std::process::abort(); }
        drop(result);
        if unsafe { h.fence.GetCompletedValue() } != 1 ||
            unsafe { h.device.GetDeviceRemovedReason() }.is_err() {
            std::process::abort();
        }
        assert_eq!(STARTED.load(Ordering::Acquire), 1);
        assert_eq!(FINISHED.load(Ordering::Acquire), 1);
        assert_eq!(*h.submitted.lock().unwrap(), 1);
        let mut expected = initial;
        expected[65528..65560].copy_from_slice(&pattern[..32]);
        expected[90016..90048].copy_from_slice(&pattern[32..]);
        expected[65528..65536].copy_from_slice(&MARK.to_le_bytes());
        assert_eq!(unsafe { std::slice::from_raw_parts(p.cast::<u8>(), N) },
                   expected.as_slice(), "actual owned shadow handback and guards");
        drop(list);
        drop(upload);
        drop(copy);
        drop(owned);
        assert!(crate::shadow::extent(A).is_none());
    }
}
