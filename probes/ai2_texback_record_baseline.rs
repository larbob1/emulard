// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to disposable pinned prepared texback.rs.
#[cfg(all(test, windows, feature = "diagnostics"))]
mod ai2_record_baseline {
    use super::*;
    use crate::resource::ai2_record_resource as guest;
    use windows::core::Interface;
    use windows::Win32::Foundation::{CloseHandle, WAIT_OBJECT_0};
    use windows::Win32::Graphics::Dxgi::{IDXGIAdapter1, DXGI_ADAPTER_FLAG_SOFTWARE};
    use windows::Win32::Graphics::Dxgi::Common::{DXGI_FORMAT_R8_UNORM, DXGI_SAMPLE_DESC};
    use windows::Win32::System::Threading::{CreateEventW, WaitForSingleObject};
    use windows_sys::Win32::System::Memory::{VirtualAlloc, VirtualFree, VirtualQuery,
        MEMORY_BASIC_INFORMATION, MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, PAGE_READWRITE, MEM_PRIVATE};

    const ALLOCATION: usize = 65536;
    const PREFIX: usize = 256;
    const SIZE: usize = 2560;
    const ACTIVE: usize = 48;
    const PAD: usize = SIZE - ACTIVE;
    const GUARD: usize = ALLOCATION - SIZE;
    const SHAPES: [(usize,usize);4] = [(7,3),(3,1),(7,3),(3,1)];
    const OFFSETS: [usize;4] = [512,0,1792,1280];

    fn pattern(i: usize, y: usize, x: usize) -> u8 {
        (11 + 43*i + 9*y + x) as u8
    }
    fn newer(i: usize) -> u8 { ((37*i + 113) & 255) as u8 }
    fn expected(published: bool, replacement: bool) -> Vec<u8> {
        let mut bytes = vec![0xE7;ALLOCATION];
        if replacement {
            for i in 0..SIZE { bytes[PREFIX+i] = newer(i); }
        }
        if published {
            for (i,(w,h)) in SHAPES.into_iter().enumerate() {
                for y in 0..h { for x in 0..w {
                    bytes[PREFIX+OFFSETS[i]+256*y+x] = pattern(i,y,x);
                }}
            }
        }
        bytes
    }

    struct Pages(*mut u8);
    impl Pages {
        fn new() -> Self {
            let p = unsafe { VirtualAlloc(std::ptr::null(), ALLOCATION,
                MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) }.cast::<u8>();
            assert!(!p.is_null());
            let pages = Self(p);
            pages.check();
            unsafe { std::ptr::write_bytes(p,0xE7,ALLOCATION); }
            pages
        }
        fn at(&self) -> usize { (unsafe { self.0.add(PREFIX) }) as usize }
        fn check(&self) {
            let mut info: MEMORY_BASIC_INFORMATION = unsafe { std::mem::zeroed() };
            let n = unsafe { VirtualQuery(self.0.cast(),&mut info,std::mem::size_of_val(&info)) };
            assert_eq!(n,std::mem::size_of_val(&info));
            assert_eq!(info.BaseAddress as usize,self.0 as usize);
            assert_eq!(info.AllocationBase as usize,self.0 as usize);
            assert_eq!(info.State,MEM_COMMIT);
            assert_eq!(info.Protect,PAGE_READWRITE);
            assert_eq!(info.Type,MEM_PRIVATE);
            assert!(info.RegionSize>=ALLOCATION);
        }
        fn verify(&self,published: bool,replacement: bool) {
            self.check();
            assert_eq!(unsafe { std::slice::from_raw_parts(self.0,ALLOCATION) },
                expected(published,replacement).as_slice());
        }
    }
    impl Drop for Pages {
        fn drop(&mut self) { assert_ne!(unsafe { VirtualFree(self.0.cast(),0,MEM_RELEASE) },0); }
    }

    fn device() -> &'static ID3D12Device {
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(),Ok("1"));
        assert_eq!(std::env::var("VICTORY_SWEEP").as_deref(),Ok("0"));
        assert_eq!(std::env::var("VICTORY_TEXTURE_BACK").as_deref(),Ok("7x3f61"));
        assert!(std::env::var_os("VICTORY_COPY_MODE").is_none());
        assert_eq!(crate::copystat::mode(),0);
        let host = crate::host::host().expect("owned WARP host");
        let adapter = crate::host::warp_adapter().expect("strict WARP");
        let d = unsafe { adapter.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        let luid = unsafe { host.device.GetAdapterLuid() };
        assert_ne!(d.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32,0);
        assert_eq!((luid.HighPart,luid.LowPart),(d.AdapterLuid.HighPart,d.AdapterLuid.LowPart));
        eprintln!("record_adapter actual_high={} actual_low={} warp_high={} warp_low={} software=1",
            luid.HighPart,luid.LowPart,d.AdapterLuid.HighPart,d.AdapterLuid.LowPart);
        &host.device
    }
    fn target(this: This,at: usize) -> Target {
        assert!(wanted(this));
        let t = Target::new(this).expect("actual target");
        assert_eq!(t.owner(),this as usize);
        assert_eq!((t.ticket.at,t.ticket.end),(at,at+SIZE));
        assert!(t.ticket.valid.load(Ordering::Acquire));
        assert_eq!((t.layout.size,t.layout.slice_size,t.layout.slices),(SIZE as u64,1280,2));
        assert_eq!((t.layout.mips[0].offset,t.layout.mips[1].offset),(512,0));
        assert_eq!((t.layout.mips[0].rows,t.layout.mips[1].rows),(3,2));
        assert_eq!((t.layout.mips[0].pitch,t.layout.mips[1].pitch),(256,256));
        assert!(t.copy.tiled.is_none());
        assert_eq!(t.copy.state.load(Ordering::Acquire),0);
        t
    }
    fn list(device: &ID3D12Device) -> (ID3D12CommandAllocator,ID3D12GraphicsCommandList) {
        unsafe {
            let a = device.CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT).unwrap();
            let l = device.CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,&a,None).unwrap();
            (a,l)
        }
    }
    fn footprints(device: &ID3D12Device,texture: &ID3D12Resource)
        -> ([D3D12_PLACED_SUBRESOURCE_FOOTPRINT;4],[u32;4],u64) {
        let desc = unsafe { texture.GetDesc() };
        assert_eq!(desc.Dimension,D3D12_RESOURCE_DIMENSION_TEXTURE2D);
        assert_eq!((desc.Width,desc.Height,desc.DepthOrArraySize,desc.MipLevels),(7,3,2,2));
        assert_eq!(desc.Format,DXGI_FORMAT_R8_UNORM);
        assert_eq!(desc.SampleDesc.Count,1);
        let mut info = D3D12_FEATURE_DATA_FORMAT_INFO{Format:desc.Format,PlaneCount:0};
        unsafe { device.CheckFeatureSupport(D3D12_FEATURE_FORMAT_INFO,
            (&mut info as *mut D3D12_FEATURE_DATA_FORMAT_INFO).cast(),
            std::mem::size_of_val(&info) as u32).unwrap(); }
        assert_eq!(info.PlaneCount,1);
        let mut f = [D3D12_PLACED_SUBRESOURCE_FOOTPRINT::default();4];
        let mut rows = [0u32;4];
        let mut row_bytes = [0u64;4];
        let mut total = 0;
        unsafe { device.GetCopyableFootprints(&desc,0,4,0,Some(f.as_mut_ptr()),
            Some(rows.as_mut_ptr()),Some(row_bytes.as_mut_ptr()),Some(&mut total)); }
        let mut extent = 0;
        for (i,(w,h)) in SHAPES.into_iter().enumerate() {
            let p = f[i].Footprint;
            assert_eq!((p.Width,p.Height,p.Depth),(w as u32,h as u32,1));
            assert_eq!(p.Format,DXGI_FORMAT_R8_UNORM);
            assert_eq!((rows[i],row_bytes[i]),(h as u32,w as u64));
            assert!(p.RowPitch>=w as u32 && p.RowPitch%256==0);
            assert_eq!(f[i].Offset%512,0);
            assert!(f[i].Offset>=extent);
            extent = f[i].Offset.checked_add(u64::from(p.RowPitch)*u64::from(rows[i])).unwrap();
        }
        assert!(total>0 && total<=extent && extent<=65536);
        (f,rows,extent)
    }
    fn upload(device: &ID3D12Device,size: u64) -> ID3D12Resource {
        let heap = D3D12_HEAP_PROPERTIES{Type:D3D12_HEAP_TYPE_UPLOAD,
            CreationNodeMask:1,VisibleNodeMask:1,..Default::default()};
        let desc = D3D12_RESOURCE_DESC{Dimension:D3D12_RESOURCE_DIMENSION_BUFFER,
            Width:size,Height:1,DepthOrArraySize:1,MipLevels:1,
            SampleDesc:DXGI_SAMPLE_DESC{Count:1,Quality:0},Layout:D3D12_TEXTURE_LAYOUT_ROW_MAJOR,
            ..Default::default()};
        let mut out: Option<ID3D12Resource> = None;
        unsafe { device.CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,
            D3D12_RESOURCE_STATE_GENERIC_READ,None,&mut out).unwrap(); }
        out.unwrap()
    }
    fn submit(device: &ID3D12Device,l: &ID3D12GraphicsCommandList) {
        let q: ID3D12CommandQueue = unsafe { device.CreateCommandQueue(&D3D12_COMMAND_QUEUE_DESC{
            Type:D3D12_COMMAND_LIST_TYPE_DIRECT,..Default::default()}).unwrap() };
        let fence: ID3D12Fence = unsafe { device.CreateFence(0,D3D12_FENCE_FLAG_NONE).unwrap() };
        let event = unsafe { CreateEventW(None,false,false,None).unwrap() };
        let cmd: ID3D12CommandList = l.cast().unwrap();
        unsafe {
            assert_eq!(fence.GetCompletedValue(),0);
            device.GetDeviceRemovedReason().unwrap();
            q.ExecuteCommandLists(&[Some(cmd)]);
            // Do not unwind or release possibly live GPU objects on uncertain completion.
            if q.Signal(&fence,1).is_err() || fence.SetEventOnCompletion(1,event).is_err()
                || WaitForSingleObject(event,30_000)!=WAIT_OBJECT_0
                || fence.GetCompletedValue()!=1 || device.GetDeviceRemovedReason().is_err() {
                std::process::abort();
            }
            CloseHandle(event).unwrap();
        }
    }

    #[test]
    #[ignore = "requires dedicated WARP fresh process"]
    fn actual_record_land_r0() {
        let d = device();
        let pages = Pages::new();
        let this = guest::create(pages.at());
        let t = target(this,pages.at());
        let retained = t.copy.clone();
        let ticket = t.ticket.clone();
        let (f,rows,extent) = footprints(d,&retained.texture);
        let up = upload(d,extent);
        let (allocator,l) = list(d);
        unsafe {
            let mut p = std::ptr::null_mut();
            up.Map(0,Some(&D3D12_RANGE{Begin:0,End:0}),Some(&mut p)).unwrap();
            assert!(!p.is_null());
            std::ptr::write_bytes(p.cast::<u8>(),0xA5,extent as usize);
            for (i,(w,h)) in SHAPES.into_iter().enumerate() {
                for y in 0..h { for x in 0..w {
                    p.cast::<u8>().add(f[i].Offset as usize+y*f[i].Footprint.RowPitch as usize+x)
                        .write(pattern(i,y,x));
                }}
            }
            up.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:extent as usize}));
            l.ResourceBarrier(&[crate::host::transition(&retained.texture,
                D3D12_RESOURCE_STATE_COMMON,D3D12_RESOURCE_STATE_COPY_DEST)]);
            for (i,fp) in f.iter().enumerate() {
                let src = D3D12_TEXTURE_COPY_LOCATION{
                    pResource:std::mem::transmute_copy(&up),Type:D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT,
                    Anonymous:D3D12_TEXTURE_COPY_LOCATION_0{PlacedFootprint:*fp}};
                let dst = D3D12_TEXTURE_COPY_LOCATION{
                    pResource:std::mem::transmute_copy(&retained.texture),Type:D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX,
                    Anonymous:D3D12_TEXTURE_COPY_LOCATION_0{SubresourceIndex:i as u32}};
                l.CopyTextureRegion(&dst,0,0,0,&src,None);
            }
            l.ResourceBarrier(&[crate::host::transition(&retained.texture,
                D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE)]);
        }
        let back = record(&l,t).expect("actual record accepted");
        assert!(Arc::ptr_eq(&back.ticket,&ticket));
        assert_eq!((back.footprints.len(),back.rows.len(),back.mips),(4,4,2));
        assert_eq!(back.range(),(pages.at(),pages.at()+SIZE));
        let width = unsafe { back.buffer.GetDesc().Width };
        assert!(width>=extent);
        for i in 0..4 {
            let a=back.footprints[i]; let b=f[i];
            assert_eq!((a.Offset,a.Footprint.Format,a.Footprint.Width,a.Footprint.Height,
                a.Footprint.Depth,a.Footprint.RowPitch,back.rows[i]),
                (b.Offset,b.Footprint.Format,b.Footprint.Width,b.Footprint.Height,
                b.Footprint.Depth,b.Footprint.RowPitch,rows[i]));
        }
        unsafe {
            l.ResourceBarrier(&[crate::host::transition(&retained.texture,
                D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_COMMON)]);
            l.Close().unwrap();
        }
        pages.verify(false,false);
        submit(d,&l);
        // Independent verification of GPU-produced active bytes before guest publication.
        unsafe {
            let mut p = std::ptr::null_mut();
            back.buffer.Map(0,Some(&D3D12_RANGE{Begin:0,End:extent as usize}),Some(&mut p)).unwrap();
            assert!(!p.is_null());
            for (i,(w,h)) in SHAPES.into_iter().enumerate() {
                for y in 0..h { for x in 0..w {
                    assert_eq!(p.cast::<u8>().add(f[i].Offset as usize+y*f[i].Footprint.RowPitch as usize+x).read(),
                        pattern(i,y,x));
                }}
            }
            back.buffer.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:0}));
        }
        pages.verify(false,false);
        land(&back);
        pages.verify(true,false);
        assert!(ticket.valid.load(Ordering::Acquire));
        guest::release(this,pages.at());
        assert!(!ticket.valid.load(Ordering::Acquire));
        drop(back); drop(l); drop(allocator); drop(up); drop(retained); drop(ticket);
        pages.verify(true,false);
        unsafe { d.GetDeviceRemovedReason().unwrap(); }
        eprintln!("record_case id=0 selected=1 recorded=1 submitted=1 fence=1 healthy=1 subresources=4 gpu_bytes={} active={} padding={} guard={} stale=0 cleanup=1 exact=1 extent={} width={}",
            ACTIVE,ACTIVE,PAD,GUARD,extent,width);
    }

    #[test]
    #[ignore = "requires dedicated WARP fresh process"]
    fn actual_record_refusal_r1() {
        let d = device();
        let pages = Pages::new();
        let old = guest::create(pages.at());
        let t = target(old,pages.at());
        let retained = t.copy.clone();
        let stale = t.ticket.clone();
        guest::release(old,pages.at());
        assert!(!stale.valid.load(Ordering::Acquire));
        let current = guest::create(pages.at());
        let new_target = target(current,pages.at());
        assert!(!Arc::ptr_eq(&stale,&new_target.ticket));
        assert!(!Arc::ptr_eq(&retained,&new_target.copy));
        unsafe { for i in 0..SIZE { (pages.at() as *mut u8).add(i).write(newer(i)); } }
        pages.verify(false,true);
        let (allocator,l) = list(d);
        // Stale ticket is refused at the entry of record. Never submit this list.
        // A regression that records anything still cannot dispatch GPU work here.
        assert!(record(&l,t).is_none());
        unsafe { l.Close().unwrap(); }
        pages.verify(false,true);
        assert!(!stale.valid.load(Ordering::Acquire));
        assert!(new_target.ticket.valid.load(Ordering::Acquire));
        guest::release(current,pages.at());
        assert!(!new_target.ticket.valid.load(Ordering::Acquire));
        drop(l); drop(allocator); drop(new_target); drop(retained); drop(stale);
        pages.verify(false,true);
        unsafe { d.GetDeviceRemovedReason().unwrap(); }
        eprintln!("record_case id=1 selected=1 recorded=0 submitted=0 fence=0 healthy=1 subresources=0 gpu_bytes=0 active=0 padding={} guard={} stale=1 cleanup=1 exact=1 newer={}",
            PAD,GUARD,SIZE);
    }
}
