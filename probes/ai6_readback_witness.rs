// SPDX-License-Identifier: GPL-3.0-or-later
// Scratch-only queue.rs append. No production configuration changes.
#[cfg(all(windows, test, feature = "diagnostics"))]
pub(crate) mod ai6_readback_witness {
    use super::*;
    use std::cell::RefCell;
    use std::io::Write;
    use windows::core::Interface;
    use windows::Win32::Graphics::Direct3D12::*;
    use windows::Win32::Graphics::Dxgi::Common::DXGI_SAMPLE_DESC;

    const INITIAL: u64 = 0x12345678_76543210;
    const MARK: u64 = 0xfedcba98_76543210; // same low half: requires wide wait
    const GUEST: u64 = 17;
    const OUT: usize = 88;
    const ROW: usize = 32;
    const PITCH: usize = 40;
    const OFFSET: usize = 4;
    const SENTINEL: [u8; OUT] = [0xe7; OUT];
    fn byte(i: usize) -> u8 { ((i * 37 + 19) % 251) as u8 }
    fn expected(consumer: bool) -> [u8; OUT] {
        let mut out = SENTINEL;
        for y in 0..2 {
            for x in 0..ROW {
                out[OFFSET + y * PITCH + x] = byte((if consumer { 1-y } else { y }) * ROW + x);
            }
        }
        out
    }

    struct Observer {
        a: usize, b: usize, marker: usize, fence: usize, consumer_queue: usize,
        phase: usize, events: [u8; 8], expected_a: [u8; OUT], expected_b: [u8; OUT],
        adverse: bool, producer_resource: usize, selected: u8, refused: u8,
        published: u8, stopped: bool,
    }
    thread_local! {
        static OBS: RefCell<Option<Observer>> = const { RefCell::new(None) };
    }
    fn require(ok: bool) {
        // Cannot unwind with pending detached lists/borrowed GPU references.
        if !ok { std::process::abort(); }
    }
    fn with_observer(f: impl FnOnce(&mut Observer)) {
        OBS.with(|slot| {
            let mut slot = slot.try_borrow_mut().unwrap_or_else(|_| std::process::abort());
            if let Some(o) = slot.as_mut() { f(o); }
        });
    }
    pub(crate) fn active() -> bool {
        OBS.with(|s| s.try_borrow().unwrap_or_else(|_| std::process::abort()).is_some())
    }
    // Fixture-owned aligned memory; sole synchronous fixture thread.
    fn marker_value(address: usize) -> u64 {
        require(address != 0 && address % 8 == 0);
        unsafe { (address as *const u64).read() }
    }
    fn bytes_at(address: usize) -> [u8; OUT] {
        // Sole fixture thread, owned initialized boxes, no reference spans a write.
        unsafe { (address as *const [u8; OUT]).read() }
    }
    fn guest(o: &Observer) -> u64 { crate::fence::completed(o.fence as This) }
    fn step(o: &mut Observer, event: u8) {
        require(o.phase == event as usize && o.phase < o.events.len());
        o.events[o.phase] = event;
        o.phase += 1;
    }

    // Called from the actual Host::submit wait gate, before FINISHED/bury.
    pub(crate) fn healthy(target: u64, completed: u64) {
        with_observer(|o| {
            require(target == completed && completed != u64::MAX);
            match o.phase {
                1 => { require(target == 1 && marker_value(o.marker) == INITIAL); step(o,1); }
                4 => { require(target == 2 && marker_value(o.marker) == MARK); step(o,4); }
                _ => std::process::abort(),
            }
            require(guest(o) == 0 && bytes_at(o.b) == SENTINEL);
        });
    }
    // Only the owned producer tuple can be skipped; B0 falls through.
    pub(crate) fn select(buffer: &ID3D12Resource, at: usize, row: usize, rows: usize, pitch: usize) -> bool {
        let mut skip = false;
        with_observer(|o| {
            if o.phase == 2 {
                require(at == o.a + OFFSET && buffer.as_raw() as usize == o.producer_resource);
                require((row,rows,pitch) == (ROW,2,PITCH) && o.selected == 0 && o.refused == 0);
                o.selected = 1;
                if o.adverse { o.refused = 1; skip = true; }
            } else {
                require(!o.adverse && o.phase == 5 && at == o.b + OFFSET);
                require((row,rows,pitch) == (ROW,2,PITCH) && o.selected == 1);
            }
        });
        skip
    }
    // Actual host read_backs returned; before any deferred writes.
    pub(crate) fn readback() {
        with_observer(|o| match o.phase {
            2 => {
                require(o.selected == 1 && o.refused == u8::from(o.adverse));
                require(bytes_at(o.a) == if o.adverse { SENTINEL } else { o.expected_a });
                require(bytes_at(o.b) == SENTINEL);
                require(marker_value(o.marker) == INITIAL && guest(o) == 0);
                step(o,2);
            }
            5 => {
                require(bytes_at(o.a) == o.expected_a && bytes_at(o.b) == o.expected_b);
                require(marker_value(o.marker) == MARK && guest(o) == 0);
                step(o,5);
            }
            _ => std::process::abort(),
        });
    }
    // Called after the actual deferred writes, before Host::submit returns.
    pub(crate) fn publication() {
        with_observer(|o| match o.phase {
            3 => {
                require(o.published == 0 && marker_value(o.marker) == MARK);
                require(bytes_at(o.a) == if o.adverse { SENTINEL } else { o.expected_a });
                require(bytes_at(o.b) == SENTINEL && guest(o) == 0);
                o.published = 1;
            }
            6 => { require(!o.adverse && o.published == 1); }
            _ => std::process::abort(),
        });
    }
    // Actual eligibility was evaluated; caller returns before removal.
    pub(super) fn stop_before_remove(q: usize, base: usize, all: bool, joining: bool,
        joined_empty: bool, next: Option<&Held>) -> bool {
        let mut stop = false;
        with_observer(|o| {
            if !o.adverse { return; }
            require(!all && !joining && joined_empty && base == 0 && q == o.consumer_queue);
            require(o.phase == 3 && o.selected == 1 && o.refused == 1 && o.published == 1 && !o.stopped);
            require(matches!(next, Some(Held::Value(w)) if w.place() == (o.marker,8)
                && w.holds_for(MARK) && !w.holds_for(INITIAL)));
            o.stopped = true;
            stop = true;
        });
        stop
    }
    // Called at actual Held::Value removal, under held/RELEASING.
    pub(super) fn released(q: usize, wait: &crate::list::ValueWait, all: bool) {
        with_observer(|o| {
            require(!o.adverse && !o.stopped && o.published == 1);
            require(!all && q == o.consumer_queue && wait.place() == (o.marker,8));
            require(marker_value(o.marker) == MARK && wait.holds_for(MARK) && !wait.holds_for(INITIAL));
            require(bytes_at(o.a) == o.expected_a && bytes_at(o.b) == SENTINEL && guest(o) == 0);
            step(o,3);
        });
    }
    // Actual Held::Signal before publication; fence::completed is an atomic load.
    pub(super) fn before_signal(q: usize, fence: usize, value: u64, all: bool) {
        with_observer(|o| {
            require(!all && q == o.consumer_queue && fence == o.fence && value == GUEST);
            require(guest(o) == 0 && marker_value(o.marker) == MARK);
            require(bytes_at(o.a) == o.expected_a && bytes_at(o.b) == o.expected_b);
            step(o,6);
        });
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
    fn actual_readback_b0() { run(false); }

    #[test]
    #[ignore = "requires isolated native WARP process; dedicated exit 86, not libtest pass"]
    fn actual_readback_b1() { run(true); }

    fn run(adverse: bool) {
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
        crate::host::ai6_readback_witness_preflight(h);
        let device = &h.device;
        let a = queue_new();
        let b = queue_new();
        let mut allocator = std::ptr::null();
        let iid = guid(0x6102dee4,0xaf59,0x4b09,[0xb9,0x99,0xb4,0x4d,0x73,0xf0,0x9b,0x24]);
        assert_eq!(crate::list::create_allocator(std::ptr::null(),0,&iid,&mut allocator),S_OK);
        assert!(!allocator.is_null());
        let la = list_new(allocator);
        let lb = list_new(allocator);
        let mut fence = std::ptr::null();
        assert_eq!(crate::fence::create(std::ptr::null(),0,0,&crate::fence::FENCE_IIDS[0],&mut fence),S_OK);
        assert!(!fence.is_null());

        let upload = buffer(device,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,64);
        let shared = buffer(device,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_COPY_DEST,64);
        let ra = buffer(device,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST,512);
        let rb = buffer(device,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST,512);
        let mut out_a = Box::new(SENTINEL);
        let mut out_b = Box::new(SENTINEL);
        let mut marker = Box::new(INITIAL);
        let pa = out_a.as_mut_ptr();
        let pb = out_b.as_mut_ptr();
        let pm = (&mut *marker) as *mut u64;
        assert_eq!(marker_value(pm as usize),INITIAL);

        unsafe {
            let mut dst = std::ptr::null_mut();
            upload.Map(0,Some(&D3D12_RANGE {Begin:0,End:0}),Some(&mut dst)).unwrap();
            assert!(!dst.is_null());
            for i in 0..64 { dst.cast::<u8>().add(i).write(byte(i)); }
            upload.Unmap(0,Some(&D3D12_RANGE {Begin:0,End:64}));
            let ha = crate::list::host_list(la).expect("producer host list");
            ha.list.CopyBufferRegion(&shared,0,&upload,0,64);
            ha.list.ResourceBarrier(&[crate::host::transition(&shared,
                D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE)]);
            ha.list.CopyBufferRegion(&ra,0,&shared,0,32);
            ha.list.CopyBufferRegion(&ra,256,&shared,32,32);
            ha.defer_read_back(ra.clone(),pa.add(OFFSET),[ROW,2,PITCH]);
            ha.defer_write(pm.cast(),Written::Value(MARK),8);
            close(la);

            // Register the real memory wait BEFORE recording B's work.
            let wait: extern "system" fn(This,u64,u32,u64) = std::mem::transmute(slot(lb,72));
            wait(lb,pm as u64,3,MARK);
            let hb = crate::list::host_list(lb).expect("consumer host list");
            hb.list.CopyBufferRegion(&rb,0,&shared,32,32);
            hb.list.CopyBufferRegion(&rb,256,&shared,0,32);
            hb.defer_read_back(rb.clone(),pb.add(OFFSET),[ROW,2,PITCH]);
            close(lb);
        }

        OBS.with(|s| {
            assert!(s.borrow().is_none());
            *s.borrow_mut() = Some(Observer { a:pa as usize,b:pb as usize,marker:pm as usize,
                fence:fence as usize,consumer_queue:b as usize,phase:0,events:[255;8],
                expected_a:expected(false),expected_b:expected(true), adverse,
                producer_resource:ra.as_raw() as usize, selected:0, refused:0, published:0, stopped:false });
        });
        execute(b,1,&lb);
        require(signal(b,fence,GUEST) == S_OK);
        {
            let held = lock(&queue(b).held);
            require(held.len() == 3);
            require(matches!(&held[0], Held::Value(w) if w.place() == (pm as usize,8)
                && w.holds_for(MARK) && !w.holds_for(INITIAL)));
            require(matches!(&held[1], Held::Run(lists,order) if lists.len()==1 && order.as_slice()==[0]));
            require(matches!(&held[2], Held::Signal(f,v) if *f==fence as usize && *v==GUEST));
        }
        require(lock(&WAITING).as_slice() == [b as usize]);
        with_observer(|o| {
            require(marker_value(o.marker)==INITIAL && guest(o)==0);
            require(bytes_at(o.a)==SENTINEL && bytes_at(o.b)==SENTINEL);
            step(o,0);
        });
        execute(a,1,&la); // real producer triggers ordinary release_held(false)
        require(!RELEASING_HERE.get());
        if adverse {
            // Execution guards have returned; separate short snapshots.
            with_observer(|o| {
                require(o.stopped && o.phase == 3 && o.events[..3] == [0,1,2]);
                require(o.selected == 1 && o.refused == 1 && o.published == 1);
                require(marker_value(o.marker) == MARK && guest(o) == 0);
                require(bytes_at(o.a) == SENTINEL && bytes_at(o.b) == SENTINEL);
            });
            require(lock(&WAITING).as_slice() == [b as usize]);
            {
                let held = lock(&queue(b).held);
                require(held.len() == 3);
                require(matches!(&held[0], Held::Value(w) if w.place() == (pm as usize,8)
                    && w.holds_for(MARK) && !w.holds_for(INITIAL)));
                require(matches!(&held[1], Held::Run(lists,order) if lists.len()==1 && order.as_slice()==[0]));
                require(matches!(&held[2], Held::Signal(f,v) if *f==fence as usize && *v==GUEST));
            }
            require(lock(&queue(a).held).is_empty());
            crate::host::ai6_readback_witness_finish(h,1);
            // Retain COM objects and boxes through dedicated process exit.
            let mut err = std::io::stderr().lock();
            if writeln!(err,"readback_case id=1 selected=1 refused=1 published=1 stopped=1 healthy_fences=1 producer_bytes=0 consumer_bytes=0 sentinel_bytes=176 guard_bytes=48 marker=wide_equal guest_fence=0 held=3 waiting=1 forced=0 retired=0 terminal=86").is_err()
                || err.flush().is_err() { std::process::abort(); }
            drop(err);
            std::process::exit(86);
        }
        with_observer(|o| {
            require(guest(o)==GUEST && marker_value(o.marker)==MARK);
            require(bytes_at(o.a)==o.expected_a && bytes_at(o.b)==o.expected_b);
            step(o,7);
        });
        require(lock(&WAITING).is_empty());
        require(lock(&queue(a).held).is_empty() && lock(&queue(b).held).is_empty());
        crate::host::ai6_readback_witness_finish(h,2);
        let observed = OBS.with(|s| s.borrow_mut().take().unwrap_or_else(|| std::process::abort()));
        assert_eq!(observed.events,[0,1,2,3,4,5,6,7]);
        assert_eq!((observed.selected,observed.refused,observed.published,observed.stopped),(1,0,1,false));
        unsafe {
            drop_object(lb); drop_object(la); drop_object(allocator);
            drop_object(fence); drop_object(b); drop_object(a);
        }
        drop((upload,shared,ra,rb,out_a,out_b,marker));
        eprintln!("readback_case id=0 selected=1 refused=0 published=1 stopped=0 healthy_fences=2 producer_bytes=64 consumer_bytes=64 guard_bytes=48 marker=wide_equal guest_fence=17 held=0 waiting=0 forced=0 retired=0 events=0,1,2,3,4,5,6,7");
    }
}
