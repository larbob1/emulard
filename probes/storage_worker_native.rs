// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only W0/W1 actual worker ownership probe, inserted into existing tests.
// NativeScratch is copied unchanged from #121; no W2, timing or runtime flag.

struct NativeScratch {
    idle: Vec<u8>,
    limit: usize,
    hits: usize,
    calls: usize,
}

impl NativeScratch {
    fn new(limit: usize) -> Self {
        Self { idle: Vec::new(), limit, hits: 0, calls: 0 }
    }

    fn trim(&mut self) {
        self.idle = Vec::new();
    }

    fn run<T, E>(&mut self, size: usize,
                 op: impl FnOnce(&mut [u8]) -> Result<T, E>) -> Result<T, E> {
        self.calls += 1;
        let mut data = std::mem::take(&mut self.idle);
        if size > self.limit || self.limit == 0 {
            data = Vec::new();
        }
        self.hits += usize::from(size != 0 && data.capacity() >= size);
        data.clear();
        data.resize(size, 0);
        let result = op(&mut data);
        if result.is_ok() && self.limit != 0 && data.capacity() <= self.limit {
            data.clear();
            self.idle = data;
        }
        result
    }
}

use std::sync::atomic::{AtomicUsize, Ordering as WorkerOrdering};
use std::sync::{Mutex as WorkerMutex, OnceLock as WorkerOnceLock};

const WORKER_CASES: usize = 10;
const WORKER_CAP: usize = 65536;
static WORKER_MODE: WorkerOnceLock<usize> = WorkerOnceLock::new();
static WORKER_ENTERED: AtomicUsize = AtomicUsize::new(0);
static WORKER_SPAWNED: AtomicUsize = AtomicUsize::new(0);

#[derive(Clone, Copy, Debug)]
struct WorkerReceipt {
    slot: usize, lane: u64, seq: u64, options: u64,
    source: usize, destination: usize, hr: HRESULT,
    before: usize, after: usize, calls: usize, hits: usize,
}
static WORKER_RECEIPTS: WorkerMutex<[Option<WorkerReceipt>; WORKER_CASES]> =
    WorkerMutex::new([None; WORKER_CASES]);

pub(super) fn worker_probe_spawned(count: usize) {
    if WORKER_MODE.get().is_some() {
        WORKER_SPAWNED.store(count, WorkerOrdering::Release);
    }
}

pub(super) struct WorkerProbe {
    slot: usize,
    scratch: Option<NativeScratch>,
}

impl WorkerProbe {
    pub(super) fn new() -> Option<Self> {
        let cap = *WORKER_MODE.get()?;
        let slot = WORKER_ENTERED.fetch_add(1, WorkerOrdering::AcqRel);
        Some(Self { slot, scratch: (cap != 0).then(|| NativeScratch::new(cap)) })
    }

    // Called only after the scheduler guard is dropped, before finish.
    pub(super) fn run(&mut self, job: &Job) -> Result<(), HRESULT> {
        let (before, after, calls, hits, result) = if let Some(scratch) = &mut self.scratch {
            let before = scratch.idle.capacity();
            let calls = scratch.calls;
            let hits = scratch.hits;
            let result = execute_scratch_review(&job.request, scratch);
            (before, scratch.idle.capacity(), scratch.calls - calls, scratch.hits - hits, result)
        } else {
            (0, 0, 0, 0, execute(&job.request))
        };
        let row = WorkerReceipt {
            slot: self.slot, lane: job.lane, seq: job.seq, options: job.request.options,
            source: job.request.source_size as usize, destination: job.request.destination_size as usize,
            hr: result.as_ref().err().copied().unwrap_or(S_OK), before, after, calls, hits,
        };
        let mut rows = WORKER_RECEIPTS.lock().unwrap_or_else(|e| e.into_inner());
        let Some(place) = rows.iter_mut().find(|r| r.is_none()) else {
            // Detached worker failure cannot safely unwind an in-flight job.
            std::process::abort();
        };
        *place = Some(row);
        result
    }
}

struct WorkerQueue(*mut c_void);
impl Drop for WorkerQueue {
    fn drop(&mut self) { void(self.0, 0x40); release(self.0.cast::<Instance<Queue>>()); }
}
struct WorkerFile(*mut c_void);
impl Drop for WorkerFile {
    fn drop(&mut self) { release(self.0.cast::<Instance<File>>()); }
}
struct WorkerArray(*mut c_void);
impl Drop for WorkerArray {
    fn drop(&mut self) { release(self.0.cast::<Instance<StatusArray>>()); }
}

fn worker_native(cap: usize) {
    assert!(WORKER_MODE.set(cap).is_ok(), "fresh process required");
    assert_eq!(std::env::var("VICTORY_DISK_WORKERS").as_deref(), Ok("1"));
    let data = pattern(256 * 1024);
    let packed = compress_zlib(&data[..4096]);
    let (_dir, file) = file_with(&data);
    let file = WorkerFile(file);
    // options, offset, source bytes, destination bytes, expected status.
    let cases = [
        (0, 7, 4096, 4096, S_OK),
        (0, 31, 4096, 4096, S_OK),
        (0, 0, 16, 8, E_INVALIDARG),
        (0, data.len()-3, 4096, 4096, END_OF_FILE),
        (0, 79, 4096, 4096, S_OK),
        (MEMORY_SOURCE, 0, 4096, 4096, S_OK),
        (ZLIB | MEMORY_SOURCE, 0, packed.len(), 4096, S_OK),
        (0, 0, 131072, 131072, S_OK),
        (0, 97, 4096, 4096, S_OK),
        (0, 121, 4096, 4096, S_OK),
    ];
    let mut destinations: Vec<Vec<u8>> = cases.iter().map(|c| vec![0xA5; c.3 + 16]).collect();
    let pointers: Vec<*mut c_void> = destinations.iter_mut().map(|b| b[8..].as_mut_ptr().cast()).collect();
    let array = WorkerArray(status_array(WORKER_CASES as u32));
    let mut observed = [E_PENDING; WORKER_CASES];
    // Queue declared after every backing object; Drop cancels unstarted jobs and waits for running jobs on unwind.
    for (first, last) in [(0, 9), (9, 10)] {
        let queue = WorkerQueue(new_queue(0));
        assert_eq!(WORKER_SPAWNED.load(WorkerOrdering::Acquire), 1);
        for i in first..last {
            let (options, offset, source, dest, expected) = cases[i];
            let input = if options == MEMORY_SOURCE {
                data.as_ptr().cast()
            } else if options == ZLIB | MEMORY_SOURCE {
                packed.as_ptr().cast()
            } else {
                file.0.cast_const()
            };
            let r = request(options, pointers[i], dest, input, offset as u64, source);
            enqueue(queue.0, &r);
            enqueue_status(queue.0, array.0, i as u32);
            void(queue.0, 0x30);
            observed[i] = wait(array.0, i as u32);
            assert_eq!(observed[i], expected);
        }
        drop(queue);
    }
    assert_eq!(WORKER_ENTERED.load(WorkerOrdering::Acquire), 1);
    let rows = *WORKER_RECEIPTS.lock().unwrap_or_else(|e| e.into_inner());
    let rows = rows.map(|r| r.expect("missing worker receipt"));
    let (remaining_lanes, staged) = {
        let lanes = scheduler().expect("existing scheduler").lock();
        (lanes.lanes.len(), lanes.staged)
    };
    assert_eq!((remaining_lanes, staged), (0, 0));
    let mut delivered = 0usize;
    let mut success = 0usize;
    let mut failed = 0usize;
    let mut guards = 0usize;
    for i in 0..WORKER_CASES {
        let (options, offset, source, dest, expected) = cases[i];
        let terminal = result(array.0, i as u32);
        assert_eq!(terminal, expected);
        assert_eq!(terminal, observed[i]);
        let mut oracle = vec![0xA5; dest + 16];
        if terminal == S_OK {
            success += 1;
            let input = if options & MEMORY_SOURCE != 0 { &data[..dest] } else { &data[offset..offset+dest] };
            oracle[8..8+dest].copy_from_slice(input);
        } else {
            assert_ne!(terminal, E_PENDING);
            failed += 1;
        }
        assert_eq!(destinations[i], oracle);
        assert_eq!(&destinations[i][..8], &[0xA5; 8]);
        assert_eq!(&destinations[i][8+dest..], &[0xA5; 8]);
        guards += destinations[i].len() - dest;
        if terminal == S_OK { delivered += destinations[i].len() - 16; }
        let r = rows[i];
        assert_eq!((r.slot, r.options, r.source, r.destination, r.hr), (0, options, source, dest, expected));
        if i > 0 {
            assert!(r.seq > rows[i-1].seq);
            assert_eq!(r.before, rows[i-1].after);
        } else {
            assert_eq!(r.before, 0);
        }
        if i < 9 { assert_eq!(r.lane, rows[0].lane); } else { assert_ne!(r.lane, rows[0].lane); }
        if cap == 0 {
            assert_eq!((r.before, r.after, r.calls, r.hits), (0, 0, 0, 0));
        } else {
            let calls = [1,1,0,1,1,0,0,1,1,1][i];
            let hits = [0,1,0,1,0,0,0,0,0,1][i];
            assert_eq!((r.calls, r.hits), (calls, hits));
            assert!(r.after <= cap);
            match i {
                3 | 7 => assert_eq!(r.after, 0),
                2 | 5 | 6 => assert_eq!(r.after, r.before),
                _ => assert!(r.after >= 4096),
            }
        }
        eprintln!("storage_worker_case index={} slot={} lane={} seq={} options={} source={} destination={} hr={} before={} after={} calls={} hits={}",
            i, r.slot, r.lane, r.seq, r.options, r.source, r.destination, r.hr, r.before, r.after, r.calls, r.hits);
    }
    assert_eq!((success, failed, delivered, guards), (8, 2, 159744, 160));
    let spawned = WORKER_SPAWNED.load(WorkerOrdering::Acquire);
    let entered = WORKER_ENTERED.load(WorkerOrdering::Acquire);
    eprintln!("storage_worker_final cap={} spawned={} entered={} cases={} success={} failed={} delivered={} guards={} remaining_lanes={} staged={}",
        cap, spawned, entered, success + failed, success, failed, delivered, guards, remaining_lanes, staged);
}

#[test]
#[ignore = "isolated single-worker baseline, fresh process and external watchdog required"]
fn storage_worker_native_baseline() { worker_native(0); }

#[test]
#[ignore = "isolated single-worker scratch retention, fresh process and external watchdog required"]
fn storage_worker_native_reuse() { worker_native(WORKER_CAP); }
