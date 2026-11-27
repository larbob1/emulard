// SPDX-License-Identifier: GPL-3.0-or-later
#[cfg(all(test, feature = "diagnostics"))]
mod ai1_warp_queue_receipt {
    use super::*;
    use windows::core::Interface;
    use windows::Win32::Foundation::{CloseHandle, WAIT_OBJECT_0};

    // Independent committed buffers: no HostList, shadow, title addresses,
    // registry, pooled allocator, or runtime submission/publication state.
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

    // Deliberately no unwind after an uncertain execution: all resource,
    // allocator, queue, fence and event handles remain alive until the
    // isolated test process is terminated. This is not a runtime policy.
    fn uncertain(reason: &str) -> ! {
        eprintln!("AI1 queue receipt unconfirmed: {reason}");
        std::process::abort()
    }

    #[test]
    fn actual_owned_queue_receipt() {
        const N: usize = 256;
        const TARGET: u64 = 1;
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(), Ok("1"));
        let adapter = warp_adapter().expect("software adapter required");
        let desc = unsafe { adapter.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32, 0);
        let mut device: Option<ID3D12Device> = None;
        unsafe { D3D12CreateDevice(&adapter, D3D_FEATURE_LEVEL_12_0, &mut device).unwrap(); }
        let device = device.expect("independent WARP device");
        let queue: ID3D12CommandQueue = unsafe {
            device.CreateCommandQueue(&D3D12_COMMAND_QUEUE_DESC {
                Type: D3D12_COMMAND_LIST_TYPE_DIRECT, ..Default::default()
            }).unwrap()
        };
        let allocator: ID3D12CommandAllocator = unsafe {
            device.CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT).unwrap()
        };
        let list: ID3D12GraphicsCommandList = unsafe {
            device.CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, &allocator, None).unwrap()
        };
        let upload = buffer(&device, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ, N as u64);
        let readback = buffer(&device, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST, N as u64);
        let mut ptr = std::ptr::null_mut();
        let no_read = D3D12_RANGE { Begin: 0, End: 0 };
        let all = D3D12_RANGE { Begin: 0, End: N };
        unsafe {
            upload.Map(0, Some(&no_read), Some(&mut ptr)).unwrap();
            assert!(!ptr.is_null());
            for i in 0..N { ptr.cast::<u8>().add(i).write((i as u8) ^ 0xa5); }
            upload.Unmap(0, Some(&all));
            // Two disjoint destination ranges; no transition required for
            // committed upload GENERIC_READ and readback COPY_DEST heaps.
            list.CopyBufferRegion(&readback, 0, &upload, 128, 128);
            list.CopyBufferRegion(&readback, 128, &upload, 0, 128);
            list.Close().unwrap();
        }
        let command: ID3D12CommandList = list.cast().unwrap();
        let fence: ID3D12Fence = unsafe { device.CreateFence(0, D3D12_FENCE_FLAG_NONE).unwrap() };
        assert_eq!(unsafe { fence.GetCompletedValue() }, 0);
        unsafe { device.GetDeviceRemovedReason().unwrap(); }
        let event = unsafe { CreateEventW(None, false, false, None).unwrap() };
        let commands = [Some(command)];
        unsafe {
            queue.ExecuteCommandLists(&commands);
            if queue.Signal(&fence, TARGET).is_err() { uncertain("signal"); }
            if fence.SetEventOnCompletion(TARGET, event).is_err() { uncertain("event registration"); }
            if WaitForSingleObject(event, 30_000) != WAIT_OBJECT_0 { uncertain("finite wait"); }
            let completed = fence.GetCompletedValue();
            if completed == u64::MAX || completed < TARGET { uncertain("completed value"); }
            if device.GetDeviceRemovedReason().is_err() { uncertain("device status"); }
            // Completion is now confirmed on the same independent fence.
            CloseHandle(event).unwrap();
            let mut out = std::ptr::null_mut();
            readback.Map(0, Some(&all), Some(&mut out)).unwrap();
            assert!(!out.is_null());
            let got = std::slice::from_raw_parts(out.cast::<u8>(), N).to_vec();
            readback.Unmap(0, Some(&no_read));
            let expected: Vec<u8> = (0..N).map(|i| ((i as u8) ^ 0x80) ^ 0xa5).collect();
            assert_eq!(got, expected, "every byte of swapped halves");
        }
        // Keep the original list, allocator, upload/readback and queue
        // in scope until the checked completion and independent byte oracle.
        drop(commands);
        drop(list);
        drop(allocator);
    }
}
