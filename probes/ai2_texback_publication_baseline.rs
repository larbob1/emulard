// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to a disposable, verified prepared texback.rs.
#[cfg(all(test, feature = "diagnostics"))]
mod ai2_publication_baseline {
    use super::*;
    use victory_formats::texture::{Desc, Dimension, Swizzle, Layout};
    use windows::core::Interface;
    use windows::Win32::Foundation::{CloseHandle, WAIT_OBJECT_0};
    use windows::Win32::Graphics::Dxgi::{IDXGIAdapter1, DXGI_ADAPTER_FLAG_SOFTWARE};
    use windows::Win32::Graphics::Dxgi::Common::{DXGI_FORMAT_R8_UNORM, DXGI_SAMPLE_DESC};
    use windows::Win32::System::Threading::{CreateEventW, WaitForSingleObject};

    const SIZE: usize = 512;
    const GUARD: usize = 32;
    const ROW: usize = 7;
    fn pattern(y: usize, x: usize) -> u8 {
        (17 + 41*y + 9*x) as u8
    }
    fn buffer(device: &ID3D12Device, kind: D3D12_HEAP_TYPE,
              state: D3D12_RESOURCE_STATES) -> ID3D12Resource {
        let heap = D3D12_HEAP_PROPERTIES {
            Type: kind, CreationNodeMask: 1, VisibleNodeMask: 1, ..Default::default()
        };
        let desc = D3D12_RESOURCE_DESC {
            Dimension: D3D12_RESOURCE_DIMENSION_BUFFER, Width: SIZE as u64,
            Height: 1, DepthOrArraySize: 1, MipLevels: 1,
            SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
            Layout: D3D12_TEXTURE_LAYOUT_ROW_MAJOR, ..Default::default()
        };
        let mut result: Option<ID3D12Resource> = None;
        unsafe { device.CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE,
            &desc, state, None, &mut result).unwrap(); }
        result.unwrap()
    }
    fn uncertain() -> ! { std::process::abort() }

    #[test]
    fn actual_land_publication_baseline() {
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(), Ok("1"));
        let mode = std::env::var("AI2_EXPECT_COPY").unwrap();
        assert!(mode == "normal" || mode == "none");
        if mode == "normal" {
            assert!(std::env::var_os("VICTORY_COPY_MODE").is_none());
            assert_eq!(crate::copystat::mode(), 0);
        } else {
            assert_eq!(std::env::var("VICTORY_COPY_MODE").as_deref(), Ok("none"));
            assert_eq!(crate::copystat::mode(), 2);
        }
        let host = crate::host::host().expect("owned WARP host");
        let device = &host.device;
        let adapter = crate::host::warp_adapter().expect("strict WARP");
        let desc = unsafe { adapter.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        let luid = unsafe { device.GetAdapterLuid() };
        assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32, 0);
        assert_eq!((luid.HighPart,luid.LowPart),(desc.AdapterLuid.HighPart,desc.AdapterLuid.LowPart));
        eprintln!("publication_adapter high={} low={} software=1",luid.HighPart,luid.LowPart);
        let upload = buffer(device,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);
        let readback = buffer(device,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
        unsafe {
            let mut p = std::ptr::null_mut();
            upload.Map(0,Some(&D3D12_RANGE{Begin:0,End:0}),Some(&mut p)).unwrap();
            assert!(!p.is_null());
            std::ptr::write_bytes(p.cast::<u8>(),0xA5,SIZE);
            for y in 0..2 { for x in 0..ROW { p.cast::<u8>().add(y*256+x).write(pattern(y,x)); } }
            upload.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:SIZE}));
        }
        let queue: ID3D12CommandQueue = unsafe { device.CreateCommandQueue(&D3D12_COMMAND_QUEUE_DESC{
            Type:D3D12_COMMAND_LIST_TYPE_DIRECT,..Default::default()
        }).unwrap() };
        let allocator: ID3D12CommandAllocator = unsafe { device.CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT).unwrap() };
        let list: ID3D12GraphicsCommandList = unsafe { device.CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,&allocator,None).unwrap() };
        unsafe { list.CopyBufferRegion(&readback,0,&upload,0,SIZE as u64); list.Close().unwrap(); }
        let command: ID3D12CommandList = list.cast().unwrap();
        let fence: ID3D12Fence = unsafe { device.CreateFence(0,D3D12_FENCE_FLAG_NONE).unwrap() };
        let event = unsafe { CreateEventW(None,false,false,None).unwrap() };
        unsafe {
            assert_eq!(fence.GetCompletedValue(),0);
            device.GetDeviceRemovedReason().unwrap();
            queue.ExecuteCommandLists(&[Some(command)]);
            if queue.Signal(&fence,1).is_err() || fence.SetEventOnCompletion(1,event).is_err()
                || WaitForSingleObject(event,30_000)!=WAIT_OBJECT_0
                || fence.GetCompletedValue()!=1 || device.GetDeviceRemovedReason().is_err() { uncertain(); }
            CloseHandle(event).unwrap();
            let mut p = std::ptr::null_mut();
            readback.Map(0,Some(&D3D12_RANGE{Begin:0,End:SIZE}),Some(&mut p)).unwrap();
            assert!(!p.is_null());
            let mut expected = [0xA5u8; SIZE];
            for y in 0..2 { for x in 0..ROW { expected[y*256+x]=pattern(y,x); } }
            assert_eq!(std::slice::from_raw_parts(p.cast::<u8>(),SIZE),&expected[..]);
            readback.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:0}));
        }
        let layout = Layout::new(&Desc{dimension:Dimension::Tex2d,width:ROW as u32,height:2,
            depth:1,mips:1,element_bytes:1,block:1,samples:1,swizzle:Swizzle::LINEAR}).unwrap();
        assert_eq!(layout.size,SIZE as u64);
        assert_eq!(layout.mips[0].pitch,256);
        let footprint = D3D12_PLACED_SUBRESOURCE_FOOTPRINT{Offset:0,Footprint:D3D12_SUBRESOURCE_FOOTPRINT{
            Format:DXGI_FORMAT_R8_UNORM,Width:ROW as u32,Height:2,Depth:1,RowPitch:256
        }};
        for stale in [false,true] {
            let mut dest = Box::new([0xE7u8; SIZE+2*GUARD]);
            let at = unsafe { dest.as_mut_ptr().add(GUARD) } as usize;
            let owner = at;
            let ticket = track(owner,at,at+SIZE);
            let back = Back{buffer:readback.clone(),footprints:vec![footprint],rows:vec![2],
                mips:1,layout:layout.clone(),ticket:ticket.clone()};
            if stale { released(owner); }
            assert_eq!(ticket.valid.load(Ordering::Acquire),!stale);
            land(&back);
            let mut expected = [0xE7u8; SIZE+2*GUARD];
            if !stale && mode=="normal" {
                for y in 0..2 { for x in 0..ROW { expected[GUARD+y*256+x]=pattern(y,x); } }
            }
            assert_eq!(*dest,expected,"full destination, padding and guards");
            assert_eq!(ticket.valid.load(Ordering::Acquire),!stale);
            eprintln!("publication_case mode={} stale={} active={} guard={} exact=1",mode,usize::from(stale),
                if !stale && mode=="normal" {14} else {0},2*GUARD);
            drop(back);
            drop(ticket);
        }
        unsafe { device.GetDeviceRemovedReason().unwrap(); }
    }
}
