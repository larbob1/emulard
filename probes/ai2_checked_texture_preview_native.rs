// SPDX-License-Identifier: GPL-3.0-or-later
// Insert only inside private checked_preview in disposable prepared texback.rs.
#[cfg(all(test, windows, feature = "diagnostics"))]
mod ai2_preview_native {
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

    fn pattern(i: usize, y: usize, x: usize, round: u8) -> u8 {
        (11 + 43*i + 9*y + x) as u8 + round
    }
    fn expected(sentinel: u8, round: Option<u8>) -> Vec<u8> {
        let mut bytes = vec![sentinel;ALLOCATION];
        if let Some(round) = round {
            for (i,(w,h)) in SHAPES.into_iter().enumerate() {
                for y in 0..h { for x in 0..w {
                    let offset = OFFSETS[i]+256*y+x;
                    bytes[PREFIX+offset] = pattern(i,y,x,round);
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
        fn reset(&self, sentinel: u8) {
            self.check();
            unsafe { std::ptr::write_bytes(self.0,sentinel,ALLOCATION); }
        }
        fn verify(&self,sentinel: u8,round: Option<u8>) {
            self.check();
            assert_eq!(unsafe { std::slice::from_raw_parts(self.0,ALLOCATION) },
                expected(sentinel,round).as_slice());
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
        let lower = f.iter().zip(rows.iter()).zip(row_bytes.iter()).map(|((fp,r),b)|
            fp.Offset + u64::from(fp.Footprint.RowPitch)*(u64::from(*r)-1) + *b).max().unwrap();
        assert!(lower<=total && total<=extent && extent<=65536);
        eprintln!("preview_footprint lower={} total={} extent={}",lower,total,extent);
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

    fn seed(up: &ID3D12Resource, f: &[D3D12_PLACED_SUBRESOURCE_FOOTPRINT;4],
        extent: u64, round: u8) {
        unsafe {
            let mut p = std::ptr::null_mut();
            up.Map(0,Some(&D3D12_RANGE{Begin:0,End:0}),Some(&mut p)).unwrap();
            if p.is_null() { up.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:0})); panic!("null upload"); }
            std::ptr::write_bytes(p.cast::<u8>(),0xA5,extent as usize);
            for (i,(w,h)) in SHAPES.into_iter().enumerate() {
                for y in 0..h { for x in 0..w {
                    p.cast::<u8>().add(f[i].Offset as usize+y*f[i].Footprint.RowPitch as usize+x)
                        .write(pattern(i,y,x,round));
                }}
            }
            up.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:extent as usize}));
        }
    }
    fn gpu(back: &Recorded, f: &[D3D12_PLACED_SUBRESOURCE_FOOTPRINT;4],
        rows: &[u32;4], extent: u64, round: u8) {
        assert_eq!(back.extent,extent as usize);
        assert_eq!(back.required,SIZE);
        assert_eq!(back.spans.len(),4);
        let width = unsafe { back.buffer.GetDesc().Width };
        assert!(width>=extent);
        let mut count=0;
        unsafe {
            let mut p=std::ptr::null_mut();
            back.buffer.Map(0,Some(&D3D12_RANGE{Begin:0,End:extent as usize}),Some(&mut p)).unwrap();
            let _guard=Mapping(&back.buffer);
            assert!(!p.is_null());
            for (i,(w,h)) in SHAPES.into_iter().enumerate() {
                let s=back.spans[i];
                assert_eq!((s.offset,s.pitch,s.rows,s.row_bytes,s.len),
                    (f[i].Offset as usize,f[i].Footprint.RowPitch as usize,rows[i] as usize,w,
                    f[i].Footprint.RowPitch as usize*h));
                for y in 0..h { for x in 0..w {
                    assert_eq!(p.cast::<u8>().add(s.offset+y*s.pitch+x).read(),pattern(i,y,x,round));
                    count+=1;
                }}
            }
        }
        assert_eq!(count,ACTIVE);
    }
    fn full(r: ExecutionReceipt, execution: u64, ordinal: usize) {
        assert_eq!(r.execution,execution);
        assert_eq!((r.selected.ordinal,r.selected.kind),(ordinal,(7,3,61)));
        let r=r.result.unwrap();
        let call=Call{attempted:true,requested:SIZE,success:true,done:SIZE};
        assert_eq!(r.required,SIZE);
        assert_eq!(r.preserve,call);
        assert_eq!(r.transfer,call);
        assert_eq!((r.tiles,r.mapped,r.unmapped,r.refusal),(4,true,true,None));
        assert_eq!(r.bytes(),ByteOutcome::Complete);
        assert_eq!(r.semantic,SemanticDelivery::Unresolved);
        eprintln!("preview_delivery execution={} ordinal={} required={} preserve_attempted={} preserve_requested={} preserve_success={} preserve_done={} transfer_attempted={} transfer_requested={} transfer_success={} transfer_done={} mapped={} unmapped={} tiles={} outcome={:?} semantic={:?} gpu_active={} padding={} guards={}",
            execution,ordinal,r.required,r.preserve.attempted as u8,r.preserve.requested,r.preserve.success as u8,r.preserve.done,
            r.transfer.attempted as u8,r.transfer.requested,r.transfer.success as u8,r.transfer.done,r.mapped as u8,r.unmapped as u8,r.tiles,r.bytes(),r.semantic,ACTIVE,PAD,GUARD);
    }
    fn recorded(inventory: &RecordingInventory, i: usize) -> &Recorded {
        match &inventory.entries[i].state { State::Recorded(b)=>b,_=>panic!("not recorded") }
    }

    #[test]
    #[ignore = "requires dedicated WARP fresh process"]
    fn actual_preview_replay() {
        let d=device();
        let pages=Pages::new();
        let this=guest::create(pages.at());
        let mut builder=RecordingBuilder::new();
        unsafe { builder.select(this).unwrap(); builder.select(this).unwrap(); }
        assert_eq!(builder.entries.len(),2);
        let texture=match &builder.entries[0].state {
            State::Pending(t)=>t.copy.texture.clone(),_=>panic!("selection refused")
        };
        let (f,rows,extent)=footprints(d,&texture);
        let up=upload(d,extent);
        let (allocator,l)=list(d);
        seed(&up,&f,extent,0);
        unsafe {
            l.ResourceBarrier(&[crate::host::transition(&texture,D3D12_RESOURCE_STATE_COMMON,D3D12_RESOURCE_STATE_COPY_DEST)]);
            for (i,fp) in f.iter().enumerate() {
                let src=D3D12_TEXTURE_COPY_LOCATION{pResource:std::mem::transmute_copy(&up),
                    Type:D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT,
                    Anonymous:D3D12_TEXTURE_COPY_LOCATION_0{PlacedFootprint:*fp}};
                let dst=D3D12_TEXTURE_COPY_LOCATION{pResource:std::mem::transmute_copy(&texture),
                    Type:D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX,
                    Anonymous:D3D12_TEXTURE_COPY_LOCATION_0{SubresourceIndex:i as u32}};
                l.CopyTextureRegion(&dst,0,0,0,&src,None);
            }
            l.ResourceBarrier(&[crate::host::transition(&texture,D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE)]);
        }
        let mut inventory=unsafe { builder.finish(&l).unwrap() };
        assert_eq!(inventory.entries.len(),2);
        let ticket0=recorded(&inventory,0).target.ticket.clone();
        let ticket1=recorded(&inventory,1).target.ticket.clone();
        assert!(!Arc::ptr_eq(&ticket0,&ticket1));
        for (i,ticket) in [&ticket0,&ticket1].into_iter().enumerate() {
            assert_eq!((ticket.owner,ticket.at,ticket.end),(this as usize,pages.at(),pages.at()+SIZE));
            assert_eq!(inventory.entries[i].selected.ordinal,i);
            assert!(ticket.valid.load(Ordering::Acquire));
        }
        unsafe {
            l.ResourceBarrier(&[crate::host::transition(&texture,D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_COMMON)]);
            l.Close().unwrap();
        }
        for (round,sentinel) in [(0u8,0xE7u8),(1,0xD3)] {
            // Prior loop has retired completely before rewriting upload/guest bytes.
            if round!=0 { seed(&up,&f,extent,round); }
            pages.reset(sentinel);
            pages.verify(sentinel,None);
            submit(d,&l);
            let execution=u64::from(round)+1;
            for i in 0..2 { gpu(recorded(&inventory,i),&f,&rows,extent,round); }
            pages.verify(sentinel,None);
            for i in 0..2 {
                // Reset between sequential deliveries to prove each writes every active byte.
                pages.reset(sentinel);
                full(unsafe { inventory.evaluate(execution,i).unwrap() },execution,i);
                pages.verify(sentinel,Some(round));
            }
            assert!(unsafe { inventory.evaluate(execution,2) }.is_none());
            pages.verify(sentinel,Some(round));
            assert_eq!(inventory.entries.len(),2);
            eprintln!("preview_execution execution={} submitted=1 fence=1 healthy=1 selected=2 recorded=2 delivered=2 missing=1 extent={} width0={} width1={}",
                execution,extent,unsafe{recorded(&inventory,0).buffer.GetDesc().Width},
                unsafe{recorded(&inventory,1).buffer.GetDesc().Width});
        }
        // All GPU commands have retired; deliberately invalidate only owned span metadata.
        // Actual landing rejects before preservation/Map; no malformed driver output.
        let saved=match &mut inventory.entries[0].state {
            State::Recorded(b)=>{let s=b.spans[0];b.spans[0].rows=0;s},_=>panic!("not recorded")
        };
        let r=unsafe {inventory.evaluate(2,0).unwrap()}.result.unwrap();
        assert_eq!((r.refusal,r.preserve,r.transfer,r.tiles,r.mapped,r.unmapped),
            (Some(Refusal::Geometry),NONE,NONE,0,false,false));
        assert_eq!(r.bytes(),ByteOutcome::NotAttempted);
        assert_eq!(r.semantic,SemanticDelivery::Unresolved);
        pages.verify(0xD3,Some(1));
        match &mut inventory.entries[0].state {State::Recorded(b)=>b.spans[0]=saved,_=>panic!("not recorded")}
        guest::release(this,pages.at());
        assert!(!ticket0.valid.load(Ordering::Acquire));
        assert!(!ticket1.valid.load(Ordering::Acquire));
        drop(inventory);drop(l);drop(allocator);drop(up);drop(texture);drop(ticket0);drop(ticket1);
        pages.verify(0xD3,Some(1));
        unsafe {d.GetDeviceRemovedReason().unwrap();}
        drop(pages);
        eprintln!("preview_replay executions=2 deliveries=4 geometry_mutated=1 geometry_refused=1 cleanup=1");
    }

    #[test]
    #[ignore = "requires dedicated WARP fresh process"]
    fn actual_preview_refusal() {
        let d=device();
        let pages=Pages::new();
        let this=guest::create(pages.at());
        let mut builder=RecordingBuilder::new();
        unsafe {builder.select(this).unwrap();}
        assert_eq!(builder.entries.len(),1);
        let ticket=match &builder.entries[0].state {State::Pending(t)=>t.ticket.clone(),_=>panic!("selection refused")};
        assert!(ticket.valid.load(Ordering::Acquire));
        guest::release(this,pages.at());
        assert!(!ticket.valid.load(Ordering::Acquire));
        // No use of the freed title resource pointer after release; retained Target only.
        let (allocator,l)=list(d);
        let inventory=unsafe{builder.finish(&l).unwrap()};
        assert_eq!(inventory.entries.len(),1);
        assert!(matches!(&inventory.entries[0].state,State::Refused(Refusal::Stale)));
        unsafe {l.Close().unwrap();}
        // Empty list is never submitted. Refused entry has no GPU copy or backing access.
        let r=unsafe {inventory.evaluate(0,0).unwrap()};
        assert_eq!((r.execution,r.selected.ordinal,r.selected.kind),(0,0,(7,3,61)));
        assert!(matches!(r.result,Err(Refusal::Stale)));
        assert!(unsafe {inventory.evaluate(0,1)}.is_none());
        let c=|requested,success,done|Call{attempted:true,requested,success,done};
        for (call,required,outcome) in [
            (NONE,SIZE,ByteOutcome::NotAttempted),(c(SIZE,true,SIZE),SIZE,ByteOutcome::Complete),
            (c(1027,true,1027),SIZE,ByteOutcome::Incomplete),(c(SIZE,true,1027),SIZE,ByteOutcome::Incomplete),
            (c(SIZE,false,0),SIZE,ByteOutcome::Unknown),(c(SIZE,false,1027),SIZE,ByteOutcome::Unknown),
            (c(SIZE,false,SIZE),SIZE,ByteOutcome::Unknown),(c(SIZE,true,SIZE+1),SIZE,ByteOutcome::Unknown),
            (c(0,true,0),SIZE,ByteOutcome::Unknown),(Call{done:1,..NONE},SIZE,ByteOutcome::Unknown),
            (NONE,0,ByteOutcome::Unknown),(c(SIZE+1,true,SIZE+1),SIZE,ByteOutcome::Unknown),
        ] {assert_eq!(classify(call,required),outcome);}
        pages.verify(0xE7,None);
        drop(inventory);drop(l);drop(allocator);drop(ticket);
        unsafe {d.GetDeviceRemovedReason().unwrap();}
        drop(pages);
        eprintln!("preview_refusal selected=1 recorded=0 stale=1 submitted=0 missing=1 classifier=12 cleanup=1");
    }
}
