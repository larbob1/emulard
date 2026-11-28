// SPDX-License-Identifier: GPL-3.0-or-later
// Scratch-only queue.rs append: direct guest signal baseline.
#[cfg(all(windows, test, feature = "diagnostics"))]
pub(crate) mod ai6_direct_signal_witness {
    use super::*;
    use std::cell::RefCell;
    use std::io::Write;
    use windows::core::Interface;
    use windows::Win32::Graphics::Direct3D12::*;
    use windows::Win32::Graphics::Dxgi::Common::DXGI_SAMPLE_DESC;

    const GUEST: u64 = 17;
    const OUT: usize = 88;
    const ROW: usize = 32;
    const PITCH: usize = 40;
    const OFFSET: usize = 4;
    const SENTINEL: [u8; OUT] = [0xff; OUT];
    fn byte(i: usize) -> u8 { ((i * 37 + 19) % 251) as u8 }
    fn expected() -> [u8; OUT] {
        let mut out = SENTINEL;
        for y in 0..2 {
            for x in 0..ROW {
                out[OFFSET + y * PITCH + x] = byte(y * ROW + x);
            }
        }
        out
    }

    struct Observer {
        at: usize, resource: usize, list: usize, fence: usize,
        adverse: bool, phase: u8, selected: u8, refused: u8,
    }
    thread_local! {
        static OBS: RefCell<Option<Observer>> = const { RefCell::new(None) };
    }
    fn require(ok: bool) { if !ok { std::process::abort(); } }
    fn with_observer(f: impl FnOnce(&mut Observer)) {
        OBS.with(|slot| {
            let mut slot = slot.try_borrow_mut().unwrap_or_else(|_| std::process::abort());
            if let Some(o) = slot.as_mut() { f(o); }
        });
    }
    pub(crate) fn active() -> bool {
        OBS.with(|s| s.try_borrow().unwrap_or_else(|_| std::process::abort()).is_some())
    }
    fn bytes_at(at: usize) -> [u8; OUT] {
        // Sole synchronous fixture thread; owned initialized box.
        unsafe { (at as *const [u8; OUT]).read() }
    }
    fn guest(o: &Observer) -> u64 { crate::fence::completed(o.fence as This) }
    fn check_data(o: &Observer) {
        require(bytes_at(o.at) == if o.adverse { SENTINEL } else { expected() });
    }
    pub(crate) fn healthy(target: u64, completed: u64) {
        with_observer(|o| {
            require(o.phase == 0 && target == 1 && completed == 1);
            require(guest(o) == 0 && bytes_at(o.at) == SENTINEL);
            o.phase = 1;
        });
    }
    pub(crate) fn select(buffer: &ID3D12Resource, at: usize, row: usize, rows: usize, pitch: usize) -> bool {
        let mut skip = false;
        with_observer(|o| {
            require(o.phase == 1 && o.selected == 0 && o.refused == 0);
            require(buffer.as_raw() as usize == o.resource && at == o.at + OFFSET);
            require((row, rows, pitch) == (ROW, 2, PITCH));
            require(guest(o) == 0 && bytes_at(o.at) == SENTINEL);
            o.selected = 1;
            if o.adverse { o.refused = 1; skip = true; }
            o.phase = 2;
        });
        skip
    }
    pub(crate) fn readback(list: usize) {
        with_observer(|o| {
            require(o.phase == 2 && list == o.list && o.selected == 1);
            require(o.refused == u8::from(o.adverse) && guest(o) == 0);
            check_data(o);
            o.phase = 3;
        });
    }
    fn empty(q: This) {
        require(!RELEASING_HERE.get());
        require(lock(&WAITING).is_empty());
        require(lock(&queue(q).held).is_empty());
    }
    fn buffer(device: &ID3D12Device, kind: D3D12_HEAP_TYPE,
              state: D3D12_RESOURCE_STATES, size: u64) -> ID3D12Resource {
        let heap = D3D12_HEAP_PROPERTIES {
            Type: kind, CreationNodeMask: 1, VisibleNodeMask: 1, ..Default::default()
        };
        let desc = D3D12_RESOURCE_DESC {
            Dimension: D3D12_RESOURCE_DIMENSION_BUFFER, Width: size, Height: 1,
            DepthOrArraySize: 1, MipLevels: 1, SampleDesc: DXGI_SAMPLE_DESC {Count:1, Quality:0},
            Layout: D3D12_TEXTURE_LAYOUT_ROW_MAJOR, ..Default::default()
        };
        let mut result: Option<ID3D12Resource> = None;
        unsafe { device.CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,
            state,None,&mut result).expect("owned buffer"); }
        result.expect("resource")
    }
    // Legacy interface checked before creating any of these objects.
    unsafe fn slot(obj: This, index: usize) -> *const () {
        unsafe { *(*(obj.cast::<*const *const ()>())).add(index) }
    }
    unsafe fn close(obj: This) {
        let f: extern "system" fn(This) -> HRESULT = unsafe { std::mem::transmute(slot(obj,9)) };
        assert_eq!(f(obj), S_OK);
    }
    unsafe fn drop_object(obj: This) {
        let f: extern "system" fn(This) -> u32 = unsafe { std::mem::transmute(slot(obj,2)) };
        assert_eq!(f(obj),0);
    }
    fn queue_new() -> This {
        let mut obj = std::ptr::null();
        assert_eq!(create(std::ptr::null(), &QueueDesc { kind:0, priority:0, flags:0, nodes:0 },
            &QUEUE_IIDS[0], &mut obj), S_OK);
        assert!(!obj.is_null()); obj
    }
    fn list_new(allocator: This) -> This {
        let iid = guid(0x7116d91c,0xe7e4,0x47ce,[0xb8,0xc6,0xec,0x81,0x68,0xf4,0x37,0xe5]);
        let mut obj = std::ptr::null();
        assert_eq!(crate::list::create_list(std::ptr::null(),0,0,allocator,std::ptr::null(),
            &iid,&mut obj),S_OK);
        assert!(!obj.is_null()); obj
    }


    #[test]
    #[ignore = "requires isolated native WARP process and exact environment"]
    fn actual_direct_signal_d0() { run(false); }

    #[test]
    #[ignore = "requires isolated native WARP process; dedicated exit 87, not libtest pass"]
    fn actual_direct_signal_d1() { run(true); }

    #[test]
    #[ignore = "requires separate isolated native WARP process"]
    fn actual_direct_signal_i0() {
        let h = preflight();
        let q = queue_new();
        let f = fence_new();
        empty(q);
        require(!active() && crate::fence::completed(f) == 0);
        require(signal(q, f, GUEST) == S_OK);
        require(crate::fence::completed(f) == GUEST);
        empty(q);
        crate::host::ai6_direct_signal_witness_finish(h, 0);
        unsafe { drop_object(f); drop_object(q); }
        eprintln!("direct_signal_case id=I0 submissions=0 selected=0 refused=0 guest_before=0 guest_after=17 signal_ok=1 held=0 waiting=0 cleanup=1");
    }

    fn preflight() -> &'static crate::host::Host {
        for (key,value) in [
            ("VICTORY_D3D12_WARP","1"), ("VICTORY_QUEUE_WAIT","1"),
            ("VICTORY_SPLIT_WAITS","0"), ("VICTORY_CUT_WAITS","0"),
            ("VICTORY_WAIT_FORCE","0"), ("VICTORY_WAIT_ASK","0"),
            ("VICTORY_LATE_WAIT","0"), ("VICTORY_ASYNC_SUBMIT","0"),
            ("VICTORY_JOIN_PARTS","0"), ("VICTORY_ASYNC_PRESENT","0"),
        ] { assert_eq!(std::env::var(key).as_deref(), Ok(value)); }
        assert!(std::env::var_os("VICTORY_GPU_TIMING").is_none());
        assert!(waits() && !split() && !cuts() && !forces() && !behind() && !join_parts());
        assert!(!RELEASING_HERE.get());
        assert!(!crate::device::newer());
        assert!(lock(&WAITING).is_empty());
        let h = crate::host::host().expect("runtime WARP host");
        crate::host::ai6_direct_signal_witness_preflight(h);
        h
    }
    fn fence_new() -> This {
        let mut f = std::ptr::null();
        assert_eq!(crate::fence::create(std::ptr::null(),0,0,&crate::fence::FENCE_IIDS[0],&mut f),S_OK);
        assert!(!f.is_null()); f
    }

    fn run(adverse: bool) {
        let h = preflight();
        let device = &h.device;
        let a = queue_new();
        let mut allocator = std::ptr::null();
        let iid = guid(0x6102dee4,0xaf59,0x4b09,[0xb9,0x99,0xb4,0x4d,0x73,0xf0,0x9b,0x24]);
        assert_eq!(crate::list::create_allocator(std::ptr::null(),0,&iid,&mut allocator),S_OK);
        assert!(!allocator.is_null());
        let la = list_new(allocator);
        let fence = fence_new();
        let upload = buffer(device,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,64);
        let shared = buffer(device,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_COPY_DEST,64);
        let ra = buffer(device,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST,512);
        let mut out_a = Box::new(SENTINEL);
        let pa = out_a.as_mut_ptr();
        let identity;
        unsafe {
            let mut dst = std::ptr::null_mut();
            upload.Map(0,Some(&D3D12_RANGE {Begin:0,End:0}),Some(&mut dst)).unwrap();
            assert!(!dst.is_null());
            for i in 0..64 { dst.cast::<u8>().add(i).write(byte(i)); }
            upload.Unmap(0,Some(&D3D12_RANGE {Begin:0,End:64}));
            let ha = crate::list::host_list(la).expect("producer host list");
            identity = std::ptr::from_ref(ha) as usize;
            ha.list.CopyBufferRegion(&shared,0,&upload,0,64);
            ha.list.ResourceBarrier(&[crate::host::transition(&shared,
                D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE)]);
            ha.list.CopyBufferRegion(&ra,0,&shared,0,32);
            ha.list.CopyBufferRegion(&ra,256,&shared,32,32);
            ha.defer_read_back(ra.clone(),pa.add(OFFSET),[ROW,2,PITCH]);
            close(la);
        }
        let ha = crate::list::host_list(la).expect("closed producer host list");
        require(std::ptr::from_ref(ha) as usize == identity);
        crate::host::ai6_direct_signal_witness_check_list(ha);
        require(crate::list::unmet_waits(&[la]).is_empty());
        empty(a);
        require(crate::fence::completed(fence) == 0 && bytes_at(pa as usize) == SENTINEL);
        OBS.with(|s| {
            assert!(s.borrow().is_none());
            *s.borrow_mut() = Some(Observer { at:pa as usize, resource:ra.as_raw() as usize,
                list:identity, fence:fence as usize, adverse, phase:0, selected:0, refused:0 });
        });
        execute(a,1,&la);
        empty(a);
        crate::host::ai6_direct_signal_witness_finish(h, 1);
        with_observer(|o| {
            require(o.phase == 3 && guest(o) == 0);
            check_data(o);
            o.phase = 4;
        });
        // Actual guest queue Signal, not a deferred marker or held signal.
        require(signal(a,fence,GUEST) == S_OK);
        empty(a);
        crate::host::ai6_direct_signal_witness_finish(h, 1);
        with_observer(|o| {
            require(o.phase == 4 && guest(o) == GUEST && o.selected == 1);
            require(o.refused == u8::from(adverse));
            check_data(o);
            o.phase = 5;
        });
        if adverse {
            // Deliberate terminal witness; retain resources through process exit.
            let mut err = std::io::stderr().lock();
            if writeln!(err,"direct_signal_case id=D1 submissions=1 selected=1 refused=1 healthy_fences=1 producer_bytes=0 sentinel_bytes=88 guard_bytes=24 marker_writes=0 guest_before=0 guest_after=17 signal_ok=1 held=0 waiting=0 cleanup=0 terminal=87").is_err()
                || err.flush().is_err() { std::process::abort(); }
            drop(err);
            std::process::exit(87);
        }
        let observed = OBS.with(|s| s.borrow_mut().take().unwrap_or_else(|| std::process::abort()));
        assert_eq!((observed.phase,observed.selected,observed.refused),(5,1,0));
        unsafe { drop_object(la); drop_object(allocator); drop_object(fence); drop_object(a); }
        drop((upload,shared,ra,out_a));
        eprintln!("direct_signal_case id=D0 submissions=1 selected=1 refused=0 healthy_fences=1 producer_bytes=64 guard_bytes=24 marker_writes=0 guest_before=0 guest_after=17 signal_ok=1 held=0 waiting=0 cleanup=1");
    }
}
