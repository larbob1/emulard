// Standalone timer handoff experiment. No HLE runtime or dispatch policy.
use std::cmp::Ordering;
use std::collections::BinaryHeap;
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

const LIMIT: Duration = Duration::from_secs(5);
type Job = Box<dyn FnOnce() + Send>;
struct Entry {
    deadline: Instant,
    seq: u64,
    job: Job,
}
impl PartialEq for Entry {
    fn eq(&self, other: &Self) -> bool {
        (self.deadline, self.seq) == (other.deadline, other.seq)
    }
}
impl Eq for Entry {}
impl PartialOrd for Entry {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> { Some(self.cmp(other)) }
}
impl Ord for Entry {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse order: earliest deadline, then oldest insertion.
        (other.deadline, other.seq).cmp(&(self.deadline, self.seq))
    }
}
struct Ready {
    entry: Entry,
    released: Instant,
}
#[derive(Default)]
struct State {
    pending: BinaryHeap<Entry>,
    next: u64,
    closed: bool,
    waiting_for: Option<Instant>,
}
#[derive(Default)]
struct Shared {
    state: Mutex<State>,
    changed: Condvar,
    observed: Condvar,
}
struct Timer {
    shared: Arc<Shared>,
    worker: Option<JoinHandle<()>>,
}
fn work(shared: Arc<Shared>, out: mpsc::Sender<Ready>) {
    let mut s = shared.state.lock().unwrap();
    loop {
        if s.closed { return; }
        if let Some(deadline) = s.pending.peek().map(|e| e.deadline) {
            let now = Instant::now();
            if deadline <= now {
                let entry = s.pending.pop().unwrap();
                s.waiting_for = None;
                drop(s);
                // Only handoff. Never call the job, never wait for completion.
                if out.send(Ready { entry, released: Instant::now() }).is_err() {
                    let mut state = shared.state.lock().unwrap();
                    state.closed = true;
                    shared.observed.notify_all();
                    return;
                }
                s = shared.state.lock().unwrap();
                continue;
            }
            s.waiting_for = Some(deadline);
            shared.observed.notify_all();
            s = shared.changed.wait_timeout(s, deadline.saturating_duration_since(now)).unwrap().0;
        } else {
            s.waiting_for = None;
            s = shared.changed.wait(s).unwrap();
        }
        // Always re-read the head after any timeout or notification.
    }
}
impl Timer {
    fn new() -> (Self, mpsc::Receiver<Ready>) {
        let shared: Arc<Shared> = Arc::default();
        let (tx, rx) = mpsc::channel();
        let state = shared.clone();
        let worker = thread::spawn(move || work(state, tx));
        (Self { shared, worker: Some(worker) }, rx)
    }
    fn schedule(&self, deadline: Instant, job: Job) -> Result<u64, Job> {
        let mut s = self.shared.state.lock().unwrap();
        if s.closed { return Err(job); }
        let seq = s.next;
        let Some(next) = seq.checked_add(1) else { return Err(job) };
        let wake = s.pending.peek().is_none_or(|head| deadline < head.deadline);
        s.next = next;
        s.pending.push(Entry { deadline, seq, job });
        if wake { self.shared.changed.notify_one(); }
        Ok(seq)
    }
    fn wait_for_head(&self, deadline: Instant) {
        let s = self.shared.state.lock().unwrap();
        let (guard, timeout) = self.shared.observed.wait_timeout_while(
            s, LIMIT, |s| s.waiting_for != Some(deadline) && !s.closed,
        ).unwrap();
        assert!(!timeout.timed_out() && guard.waiting_for == Some(deadline) && !guard.closed, "timer did not observe head");
    }
    fn stop(&mut self) {
        {
            let mut s = self.shared.state.lock().unwrap();
            s.closed = true;
            self.shared.changed.notify_all();
        }
        if let Some(worker) = self.worker.take() { worker.join().unwrap(); }
        // Dispose pending payloads outside the lock. Fixture-only shutdown.
        let pending = {
            let mut s = self.shared.state.lock().unwrap();
            std::mem::take(&mut s.pending)
        };
        drop(pending);
    }
}
impl Drop for Timer { fn drop(&mut self) { self.stop(); } }
fn submit(timer: &Timer, deadline: Instant, job: Job) -> u64 {
    timer.schedule(deadline, job).unwrap_or_else(|_| panic!("fixture submit refused"))
}
fn ready(rx: &mpsc::Receiver<Ready>) -> Entry {
    let r = rx.recv_timeout(LIMIT).expect("timer handoff watchdog");
    assert!(r.released >= r.entry.deadline, "early timer handoff");
    r.entry
}

#[test]
fn earlier_insert_wakes_waiter() {
    let (timer, rx) = Timer::new();
    let late = Instant::now() + Duration::from_secs(60);
    submit(&timer, late, Box::new(|| {}));
    timer.wait_for_head(late);
    let id = submit(&timer, Instant::now(), Box::new(|| {}));
    assert_eq!(ready(&rx).seq, id);
    assert!(rx.try_recv().is_err());
}
#[test]
fn same_deadline_handoff_fifo_and_not_early() {
    let (timer, rx) = Timer::new();
    let deadline = Instant::now() + Duration::from_millis(30);
    let ids: Vec<_> = (0..32).map(|_| submit(&timer, deadline, Box::new(|| {}))).collect();
    for id in ids { assert_eq!(ready(&rx).seq, id); }
    assert!(rx.try_recv().is_err());
}
#[test]
fn empty_notification_does_not_release_future_entry() {
    let (timer, rx) = Timer::new();
    let deadline = Instant::now() + Duration::from_secs(60);
    submit(&timer, deadline, Box::new(|| {}));
    timer.wait_for_head(deadline);
    { let _s = timer.shared.state.lock().unwrap(); timer.shared.changed.notify_all(); }
    assert_eq!(rx.recv_timeout(Duration::from_millis(20)).err(), Some(mpsc::RecvTimeoutError::Timeout));
    assert_eq!(timer.shared.state.lock().unwrap().pending.len(), 1);
}
#[test]
fn blocked_dispatch_does_not_stop_timer_handoff() {
    let (timer, rx) = Timer::new();
    let (entered_tx, entered_rx) = mpsc::channel();
    let (release_tx, release_rx) = mpsc::channel();
    submit(&timer, Instant::now(), Box::new(move || {
        entered_tx.send(()).unwrap();
        release_rx.recv_timeout(LIMIT).expect("dispatch release watchdog");
    }));
    let first = ready(&rx);
    let dispatched = thread::spawn(first.job);
    entered_rx.recv_timeout(LIMIT).unwrap();
    let (done_tx, done_rx) = mpsc::channel();
    let next = submit(&timer, Instant::now(), Box::new(move || { done_tx.send(()).unwrap(); }));
    let second = ready(&rx);
    assert_eq!(second.seq, next);
    // Separate dispatch chosen by test harness, not by timer service.
    thread::spawn(second.job).join().unwrap();
    done_rx.recv_timeout(LIMIT).unwrap();
    release_tx.send(()).unwrap();
    dispatched.join().unwrap();
}
#[test]
fn payload_lifetime_until_dispatch() {
    let (timer, rx) = Timer::new();
    let owner = Arc::new(());
    let weak = Arc::downgrade(&owner);
    let held = owner.clone();
    submit(&timer, Instant::now(), Box::new(move || drop(held)));
    drop(owner);
    let entry = ready(&rx);
    assert!(weak.upgrade().is_some());
    (entry.job)();
    assert!(weak.upgrade().is_none());
}
#[test]
fn fixture_stop_releases_pending_and_refuses_new_jobs() {
    let (mut timer, _rx) = Timer::new();
    let owner = Arc::new(());
    let weak = Arc::downgrade(&owner);
    submit(&timer, Instant::now() + Duration::from_secs(60), Box::new(move || drop(owner)));
    timer.stop();
    assert!(weak.upgrade().is_none());
    assert!(timer.schedule(Instant::now(), Box::new(|| {})).is_err());
}
#[test]
fn sequence_exhaustion_refuses_without_wrapping() {
    let (timer, _rx) = Timer::new();
    timer.shared.state.lock().unwrap().next = u64::MAX;
    assert!(timer.schedule(Instant::now(), Box::new(|| {})).is_err());
    assert!(timer.shared.state.lock().unwrap().pending.is_empty());
}
