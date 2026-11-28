// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to disposable pinned prepared texback.rs.
#[cfg(all(test, windows, feature = "diagnostics"))]
mod ai2_checked_landing {
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
    fn expected(limit: usize) -> Vec<u8> {
        let mut bytes = vec![0xE7;ALLOCATION];
        if limit != 0 {
            for (i,(w,h)) in SHAPES.into_iter().enumerate() {
                for y in 0..h { for x in 0..w {
                    let offset = OFFSETS[i]+256*y+x;
                    if offset < limit { bytes[PREFIX+offset] = pattern(i,y,x); }
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
        fn verify(&self,limit: usize) {
            self.check();
            assert_eq!(unsafe { std::slice::from_raw_parts(self.0,ALLOCATION) },
                expected(limit).as_slice());
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
        assert!(std::env::var_os("VICTORY_COPY_ASK").is_none());
        assert_eq!(crate::copystat::mode(),0);
        let host = crate::host::host().expect("owned WARP host");
        let adapter = crate::host::warp_adapter().expect("strict WARP");
        let d = unsafe { adapter.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        let luid = unsafe { host.device.GetAdapterLuid() };
        assert_ne!(d.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32,0);
        assert_eq!((luid.HighPart,luid.LowPart),(d.AdapterLuid.HighPart,d.AdapterLuid.LowPart));
        eprintln!("checked_adapter actual_high={} actual_low={} warp_high={} warp_low={} software=1",
            luid.HighPart,luid.LowPart,d.AdapterLuid.HighPart,d.AdapterLuid.LowPart);
        &host.device
    }
    fn target(this: This,at: usize) -> Target {
        assert!(wanted(this));
        let t = Target::new(this).expect("actual target");
        assert_eq!(t.owner(),this as usize);
        assert_eq!((t.ticket.at,t.ticket.end),(at,at+SIZE));
        assert!(t.ticket.valid.load(Ordering::Acquire));
        assert!(t.is_current());
        assert_eq!(crate::resource::texture_kind(this),Some((7,3,61)));
        let desc = &t.layout.desc;
        assert_eq!(desc.dimension,victory_formats::texture::Dimension::Tex2d);
        assert_eq!(desc.swizzle,victory_formats::texture::Swizzle::LINEAR);
        assert_eq!((desc.width,desc.height,desc.depth,desc.mips,desc.element_bytes,desc.block,desc.samples),(7,3,2,2,1,1,1));
        assert_eq!(t.layout.mips.len(),2);
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
            extent = f[i].Offset.checked_add(u64::from(p.RowPitch).checked_mul(u64::from(rows[i])).unwrap()).unwrap();
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

    const CUT: usize = 1027;
    #[derive(Clone,Copy,Debug,PartialEq,Eq)]
    enum Case { Full, PreserveRefuse, FinalRefuse, Prefix }
    #[derive(Clone,Copy,Debug,PartialEq,Eq)]
    enum Outcome { NotAttempted, Complete, Incomplete, Unknown }
    #[derive(Clone,Copy,Debug,PartialEq,Eq)]
    struct Call { attempted: bool, requested: usize, success: bool, done: usize }
    const NONE: Call = Call { attempted:false,requested:0,success:false,done:0 };
    fn classify(call: Call, required: usize) -> Outcome {
        if required == 0 { return Outcome::Unknown; }
        if !call.attempted {
            return if call == NONE { Outcome::NotAttempted } else { Outcome::Unknown };
        }
        if !call.success || call.requested == 0 || call.requested > required
            || call.done > call.requested { return Outcome::Unknown; }
        if call.requested == required && call.done == required { Outcome::Complete }
        else { Outcome::Incomplete }
    }
    // Same process, stable owned writable pages only. No fallback or retry.
    fn checked_copy(dst: *mut u8, src: *const u8, len: usize) -> Call {
        use windows_sys::Win32::System::Diagnostics::Debug::ReadProcessMemory;
        use windows_sys::Win32::System::Threading::GetCurrentProcess;
        let mut done = 0usize;
        let success = unsafe { ReadProcessMemory(GetCurrentProcess(),src.cast(),dst.cast(),len,&mut done) != 0 };
        Call { attempted:true,requested:len,success,done }
    }
    struct Receipt {
        preserve: Call, transfer: Call, tiles: usize, mapped: bool, unmapped: bool,
        staged: [u8;SIZE], valid: bool,
    }
    impl Receipt {
        fn new() -> Self { Self { preserve:NONE,transfer:NONE,tiles:0,mapped:false,unmapped:false,
            staged:[0;SIZE],valid:false } }
    }
    // Test-only derivative of raw land. No production caller, no observer,
    // no changes to generic helpers. Existing mapping -> ticket lock order.
    fn checked_land(back: &Back, ticket: &Arc<Ticket>, at: usize, case: Case) -> Receipt {
        let mut r = Receipt::new();
        let _mapping = crate::watch::title_memory_reading();
        let _ticket_guard = TICKETS.lock().unwrap_or_else(|e| e.into_inner());
        if !Arc::ptr_eq(&back.ticket,ticket) || !back.ticket.valid.load(Ordering::Acquire)
            || back.range() != (at,at.checked_add(SIZE).unwrap())
            || back.layout.size != SIZE as u64 || back.mips != 2
            || back.footprints.len()!=4 || back.rows.len()!=4 { return r; }
        let width = unsafe { back.buffer.GetDesc().Width };
        let mut ends = [(0usize,0usize,0usize);4];
        let mut previous_end = 0usize;
        for (i,(w,h)) in SHAPES.into_iter().enumerate() {
            let fp=back.footprints[i]; let f=fp.Footprint;
            if f.Format!=DXGI_FORMAT_R8_UNORM || (f.Width,f.Height,f.Depth)!=(w as u32,h as u32,1)
                || back.rows[i]!=h as u32 || f.RowPitch < w as u32 || f.RowPitch%256!=0
                || fp.Offset%512!=0 { return r; }
            let Ok(offset)=usize::try_from(fp.Offset) else { return r; };
            let Ok(pitch)=usize::try_from(f.RowPitch) else { return r; };
            let Some(len)=pitch.checked_mul(h) else { return r; };
            let Some(end)=offset.checked_add(len) else { return r; };
            if offset<previous_end || end as u64>width || end>isize::MAX as usize { return r; }
            ends[i]=(offset,pitch,len); previous_end=end;
        }
        r.valid=true;
        if case==Case::PreserveRefuse { return r; }
        let mut tiled=[0u8;SIZE];
        r.preserve=checked_copy(tiled.as_mut_ptr(),at as *const u8,SIZE);
        if classify(r.preserve,SIZE)!=Outcome::Complete { return r; }
        let mut data=std::ptr::null_mut();
        unsafe {
            if back.buffer.Map(0,None,Some(&mut data)).is_err() { return r; }
            r.mapped=true;
            if !data.is_null() {
                for (i,(offset,pitch,len)) in ends.into_iter().enumerate() {
                    let linear=std::slice::from_raw_parts(data.cast::<u8>().add(offset),len);
                    if back.layout.tile(&mut tiled,i as u32%2,i as u32/2,linear,pitch,len).is_err() { break; }
                    r.tiles+=1;
                }
            }
            back.buffer.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:0}));
            r.unmapped=true;
        }
        if r.tiles!=4 { return r; }
        r.staged=tiled;
        if case==Case::FinalRefuse { return r; }
        // Preserve the existing write-watch side effect before any transfer.
        let requested=if case==Case::Prefix {CUT} else {SIZE};
        crate::watch::writing(at,SIZE);
        r.transfer=checked_copy(at as *mut u8,tiled.as_ptr(),requested);
        r
    }

    fn classifier_check() {
        let call=|requested,success,done| Call {attempted:true,requested,success,done};
        for (c,out) in [
            (NONE,Outcome::NotAttempted),
            (call(SIZE,true,SIZE),Outcome::Complete),
            (call(CUT,true,CUT),Outcome::Incomplete),
            (call(SIZE,true,CUT),Outcome::Incomplete),
            (call(SIZE,false,0),Outcome::Unknown),
            (call(SIZE,false,CUT),Outcome::Unknown),
            (call(SIZE,false,SIZE),Outcome::Unknown),
            (call(SIZE,true,SIZE+1),Outcome::Unknown),
            (call(0,true,0),Outcome::Unknown),
            (Call {done:1,..NONE},Outcome::Unknown),
        ] { assert_eq!(classify(c,SIZE),out); }
    }
    fn run(case: Case) {
        classifier_check();
        let d = device();
        let pages = Pages::new();
        let this = guest::create(pages.at());
        let intent = this as usize;
        assert!(wanted(this));
        let t = target(this,pages.at());
        assert_eq!(t.owner(),intent);
        let retained = t.copy.clone();
        let ticket = t.ticket.clone();
        let (f,rows,extent) = footprints(d,&retained.texture);
        let up = upload(d,extent);
        let (allocator,l) = list(d);
        unsafe {
            let mut p = std::ptr::null_mut();
            up.Map(0,Some(&D3D12_RANGE{Begin:0,End:0}),Some(&mut p)).unwrap();
            if p.is_null() { up.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:0})); panic!("null upload mapping"); }
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
        pages.verify(0);
        submit(d,&l);
        // Independent verification of GPU-produced active bytes before guest publication.
        let mut gpu_active = 0usize;
        unsafe {
            let mut p = std::ptr::null_mut();
            back.buffer.Map(0,Some(&D3D12_RANGE{Begin:0,End:extent as usize}),Some(&mut p)).unwrap();
            if p.is_null() { back.buffer.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:0})); panic!("null readback mapping"); }
            for (i,(w,h)) in SHAPES.into_iter().enumerate() {
                for y in 0..h { for x in 0..w {
                    assert_eq!(p.cast::<u8>().add(f[i].Offset as usize+y*f[i].Footprint.RowPitch as usize+x).read(),
                        pattern(i,y,x));
                    assert_ne!(pattern(i,y,x),0xE7);
                    gpu_active += 1;
                }}
            }
            back.buffer.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:0}));
        }
        assert_eq!(gpu_active,ACTIVE);
        pages.verify(0);
        let receipt=checked_land(&back,&ticket,pages.at(),case);
        assert!(receipt.valid);
        let preserved=case!=Case::PreserveRefuse;
        let limit=match case {Case::Full=>SIZE,Case::Prefix=>CUT,_=>0};
        let required=if preserved { Call {attempted:true,requested:SIZE,success:true,done:SIZE} } else {NONE};
        assert_eq!(receipt.preserve,required);
        assert_eq!((receipt.tiles,receipt.mapped,receipt.unmapped),(if preserved {4} else {0},preserved,preserved));
        if preserved { assert_eq!(&receipt.staged[..],&expected(SIZE)[PREFIX..PREFIX+SIZE]); }
        else { assert_eq!(receipt.staged,[0;SIZE]); }
        assert_eq!(receipt.transfer,if limit==0 {NONE} else {Call {attempted:true,requested:limit,success:true,done:limit}});
        let outcome=classify(receipt.transfer,SIZE);
        assert_eq!(outcome,match case {Case::Full=>Outcome::Complete,Case::Prefix=>Outcome::Incomplete,_=>Outcome::NotAttempted});
        pages.verify(limit);
        let initial=expected(0);
        let actual=unsafe {std::slice::from_raw_parts(pages.0,ALLOCATION)};
        let published=actual.iter().zip(&initial).filter(|(x,y)|x!=y).count();
        assert_eq!(published,match case {Case::Full=>48,Case::Prefix=>20,_=>0});
        assert!(ticket.valid.load(Ordering::Acquire));
        guest::release(this,pages.at());
        assert!(!ticket.valid.load(Ordering::Acquire));
        drop(back); drop(l); drop(allocator); drop(up); drop(retained); drop(ticket);
        pages.verify(limit);
        unsafe { d.GetDeviceRemovedReason().unwrap(); }
        drop(pages);
        eprintln!("checked_case mode={:?} selected=1 recorded=1 submitted=1 fence=1 healthy=1 obligation={} preserve_attempted={} preserve_requested={} preserve_success={} preserve_done={} tiles={} mapped={} unmapped={} transfer_attempted={} transfer_requested={} transfer_success={} transfer_done={} outcome={:?} gpu_active={} published_active={} preserved={} guards={} cleanup=1 extent={} width={} classifier=10",
            case,SIZE,receipt.preserve.attempted as u8,receipt.preserve.requested,receipt.preserve.success as u8,receipt.preserve.done,
            receipt.tiles,receipt.mapped as u8,receipt.unmapped as u8,receipt.transfer.attempted as u8,receipt.transfer.requested,
            receipt.transfer.success as u8,receipt.transfer.done,outcome,gpu_active,published,PAD,GUARD,extent,width);
    }

    #[test]
    #[ignore = "requires dedicated WARP fresh process"]
    fn actual_checked_full() { run(Case::Full); }
    #[test]
    #[ignore = "requires dedicated WARP fresh process"]
    fn actual_checked_preserve_refuse() { run(Case::PreserveRefuse); }
    #[test]
    #[ignore = "requires dedicated WARP fresh process"]
    fn actual_checked_final_refuse() { run(Case::FinalRefuse); }
    #[test]
    #[ignore = "requires dedicated WARP fresh process"]
    fn actual_checked_prefix() { run(Case::Prefix); }
}
