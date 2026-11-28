// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only W0/W1 backing-ownership observations, derived from #123/#126.
// Capacity and live identity, not allocator calls, RSS, idle trim or timing.

#[derive(Clone, Copy, Debug, Default)]
struct Ownership {
    requested: usize, take: usize, discard: usize, fresh: usize,
    active: usize, same_live: usize, same_retained: usize,
    retain: usize, drop_work: usize, untouched: usize,
}

struct NativeScratch {
    idle: Vec<u8>,
    limit: usize,
    hits: usize,
    calls: usize,
    last: Ownership,
}

impl NativeScratch {
    fn new(limit: usize) -> Self {
        Self { idle: Vec::new(), limit, hits: 0, calls: 0, last: Ownership::default() }
    }

    fn run<T, E>(&mut self, size: usize,
                 op: impl FnOnce(&mut [u8]) -> Result<T, E>) -> Result<T, E> {
        self.calls += 1;
        // A retained Vec is empty after clear(), but can own live backing.
        let mut event = Ownership { requested: size, ..Ownership::default() };
        let mut data = std::mem::take(&mut self.idle);
        event.take = usize::from(data.capacity() > 0);
        if size > self.limit || self.limit == 0 {
            event.discard = usize::from(data.capacity() > 0);
            data = Vec::new();
        }
        let available = data.capacity();
        let hit = size != 0 && available >= size;
        // Capture a pointer only when resize cannot reallocate.
        let live = if hit { Some(data.as_ptr()) } else { None };
        self.hits += usize::from(hit);
        data.clear();
        data.resize(size, 0);
        let result = op(&mut data);
        event.active = data.capacity();
        event.fresh = usize::from(available == 0 && event.active > 0);
        event.same_live = usize::from(live.is_some_and(|p| p == data.as_ptr() && available == data.capacity()));
        if result.is_ok() && self.limit != 0 && data.capacity() <= self.limit {
            data.clear();
            event.retain = usize::from(data.capacity() > 0);
            self.idle = data;
            event.same_retained = usize::from(live.is_some_and(|p| p == self.idle.as_ptr() && available == self.idle.capacity()));
        } else {
            event.drop_work = usize::from(data.capacity() > 0);
            drop(data);
        }
        // No pointer is stored or compared after release.
        self.last = event;
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
    observed: usize, ownership: Ownership,
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
        let (before, after, calls, hits, observed, ownership, result) = if let Some(scratch) = &mut self.scratch {
            let before = scratch.idle.capacity();
            let calls = scratch.calls;
            let hits = scratch.hits;
            let live = if before > 0 { Some(scratch.idle.as_ptr()) } else { None };
            scratch.last = Ownership::default();
            let result = execute_scratch_review(&job.request, scratch);
            let after = scratch.idle.capacity();
            let entered = scratch.calls - calls;
            // Only run can mutate idle. If no entry, backing remains live.
            if entered == 0 {
                scratch.last.untouched = usize::from(before == after
                    && live.is_none_or(|p| p == scratch.idle.as_ptr()));
            }
            (before, after, entered, scratch.hits - hits, 1, scratch.last, result)
        } else {
            // W0 is deliberately not instrumented at the bounce allocation.
            (0, 0, 0, 0, 0, Ownership::default(), execute(&job.request))
        };
        let row = WorkerReceipt {
            slot: self.slot, lane: job.lane, seq: job.seq, options: job.request.options,
            source: job.request.source_size as usize, destination: job.request.destination_size as usize,
            hr: result.as_ref().err().copied().unwrap_or(S_OK), before, after, calls, hits, observed, ownership,
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

#[derive(Clone, Copy, Debug, Default)]
struct Drain {
    lanes: usize, lane: u64, closed: usize, reads: usize, running: usize,
    held: usize, unsubmitted: usize, statuses: usize, failures: usize, staged: u64,
}

fn drain_snapshot() -> Drain {
    // Caller holds neither receipt nor scheduler guard; no logging/allocation inside.
    let lanes = scheduler().expect("existing scheduler").lock();
    let mut out = Drain { lanes: lanes.lanes.len(), staged: lanes.staged, ..Drain::default() };
    for (&id, lane) in &lanes.lanes {
        out.lane = id;
        out.closed += usize::from(lane.closed);
        out.reads += lane.reads.len();
        out.running += lane.running.len();
        out.held += lane.held.len();
        out.unsubmitted += lane.unsubmitted.len();
        out.statuses += lane.statuses.len();
        out.failures += lane.failures.len();
    }
    out
}

fn check_drain(d: Drain, expected_lane: Option<u64>) {
    assert_eq!(d.lanes, usize::from(expected_lane.is_some()));
    if let Some(id) = expected_lane { assert_eq!(d.lane, id); }
    assert_eq!((d.closed, d.reads, d.running, d.held, d.unsubmitted, d.statuses, d.failures, d.staged),
        (0, 0, 0, 0, 0, 0, 0, 0));
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
    let mut drains = [Drain::default(); 3];
    // Queue declared after every backing object; Drop cancels unstarted jobs and waits for running jobs on unwind.
    for (phase, (first, last)) in [(0, 9), (9, 10)].into_iter().enumerate() {
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
        // SAFETY: WorkerQueue still owns the live queue reference on this thread.
        let id = unsafe { &*queue.0.cast::<Instance<Queue>>() }.state.id;
        // Terminal status was acquired before this independent scheduler snapshot.
        drains[phase] = drain_snapshot();
        check_drain(drains[phase], Some(id));
        drop(queue);
    }
    drains[2] = drain_snapshot();
    check_drain(drains[2], None);
    assert_eq!(WORKER_ENTERED.load(WorkerOrdering::Acquire), 1);
    let rows = *WORKER_RECEIPTS.lock().unwrap_or_else(|e| e.into_inner());
    let rows = rows.map(|r| r.expect("missing worker receipt"));
    let (remaining_lanes, staged) = (drains[2].lanes, drains[2].staged);
    let (mut take, mut discard, mut fresh, mut retain, mut drop_work) = (0, 0, 0, 0, 0);
    let (mut success_hits, mut failed_hits) = (0, 0);
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
        assert_eq!(r.lane, drains[if i < 9 { 0 } else { 1 }].lane);
        let o = r.ownership;
        if cap == 0 {
            assert_eq!((r.before, r.after, r.calls, r.hits, r.observed), (0, 0, 0, 0, 0));
            assert_eq!((o.requested, o.take, o.discard, o.fresh, o.active, o.same_live,
                o.same_retained, o.retain, o.drop_work, o.untouched), (0,0,0,0,0,0,0,0,0,0));
        } else {
            assert_eq!(r.observed, 1);
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
        if cap != 0 {
            if r.calls == 0 {
                assert_eq!((o.requested, o.take, o.discard, o.fresh, o.active, o.same_live,
                    o.same_retained, o.retain, o.drop_work, o.untouched), (0,0,0,0,0,0,0,0,0,1));
            } else {
                assert_eq!(o.requested, source);
                assert_eq!(o.untouched, 0);
                assert_eq!(o.take, usize::from(r.before > 0));
                assert_eq!(o.discard, usize::from(r.before > 0 && source > cap));
                let available = if o.discard != 0 { 0 } else { r.before };
                assert!(o.active >= source);
                assert_eq!(o.fresh, usize::from(available == 0));
                assert_eq!(r.hits, usize::from(available >= source));
                assert_eq!(o.same_live, r.hits);
                if r.hits != 0 { assert_eq!(o.active, available); }
                let retained = usize::from(terminal == S_OK && o.active <= cap);
                assert_eq!((o.retain, o.drop_work), (retained, 1-retained));
                assert_eq!(r.after, if retained != 0 { o.active } else { 0 });
                assert_eq!(o.same_retained, r.hits * retained);
                assert_eq!(o.take - o.discard + o.fresh, o.retain + o.drop_work);
                if terminal == S_OK { success_hits += r.hits; } else { failed_hits += r.hits; }
            }
            take += o.take; discard += o.discard; fresh += o.fresh;
            retain += o.retain; drop_work += o.drop_work;
        }
        eprintln!("storage_ownership_case index={} slot={} lane={} seq={} options={} source={} destination={} hr={} before={} after={} calls={} hits={} observed={} requested={} take={} discard={} fresh={} active={} same_live={} same_retained={} retain={} drop_work={} untouched={}",
            i, r.slot, r.lane, r.seq, r.options, r.source, r.destination, r.hr, r.before, r.after, r.calls, r.hits,
            r.observed, o.requested, o.take, o.discard, o.fresh, o.active, o.same_live, o.same_retained, o.retain, o.drop_work, o.untouched);
    }
    assert_eq!((success, failed, delivered, guards), (8, 2, 159744, 160));
    let spawned = WORKER_SPAWNED.load(WorkerOrdering::Acquire);
    let entered = WORKER_ENTERED.load(WorkerOrdering::Acquire);
    let final_capacity = rows[WORKER_CASES-1].after;
    let expected = if cap == 0 { (0,0,0,0,0,0,0) } else { (4,1,4,5,2,2,1) };
    assert_eq!((take, discard, fresh, retain, drop_work, success_hits, failed_hits), expected);
    assert_eq!(fresh, discard + drop_work + usize::from(final_capacity > 0));
    for (phase, d) in drains.iter().enumerate() {
        eprintln!("storage_ownership_drain phase={} lanes={} lane={} closed={} reads={} running={} held={} unsubmitted={} statuses={} failures={} staged={}",
            phase, d.lanes, d.lane, d.closed, d.reads, d.running, d.held, d.unsubmitted, d.statuses, d.failures, d.staged);
    }
    eprintln!("storage_ownership_final cap={} spawned={} entered={} cases={} success={} failed={} delivered={} guards={} remaining_lanes={} staged={} take={} discard={} fresh={} retain={} drop_work={} success_hits={} failed_hits={} last_capacity={}",
        cap, spawned, entered, success + failed, success, failed, delivered, guards, remaining_lanes, staged,
        take, discard, fresh, retain, drop_work, success_hits, failed_hits, final_capacity);
}

#[test]
#[ignore = "isolated single-worker baseline, fresh process and external watchdog required"]
fn storage_worker_ownership_native_baseline() { worker_native(0); }

#[test]
#[ignore = "isolated single-worker scratch retention, fresh process and external watchdog required"]
fn storage_worker_ownership_native_reuse() { worker_native(WORKER_CAP); }
