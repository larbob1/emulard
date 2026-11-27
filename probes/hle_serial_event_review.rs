// Standalone explicit-owner serialized worker model; not HLE Port or Queue.
use std::collections::VecDeque;
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread::{self, JoinHandle};
use std::time::Duration;

const LIMIT: Duration = Duration::from_secs(5);
type Job = Box<dyn FnOnce() + Send>;
struct State {
    owners: usize,
    jobs: VecDeque<Job>,
    waiting: bool,
    ended: bool,
}
struct Shared {
    state: Mutex<State>,
    ready: Condvar,
    observed: Condvar,
}
struct Owner(Arc<Shared>);
impl Clone for Owner {
    fn clone(&self) -> Self {
        let mut s = self.0.state.lock().unwrap();
        assert!(s.owners > 0);
        s.owners = s.owners.checked_add(1).expect("fixture owner overflow");
        Self(self.0.clone())
    }
}
impl Drop for Owner {
    fn drop(&mut self) {
        let mut s = self.0.state.lock().unwrap();
        s.owners -= 1;
        if s.owners == 0 { self.0.ready.notify_one(); }
        // Never join or run callbacks here.
    }
}
impl Owner {
    fn submit(&self, job: Job) {
        let mut s = self.0.state.lock().unwrap();
        assert!(s.owners > 0 && !s.ended);
        s.jobs.push_back(job);
        self.0.ready.notify_one();
    }
}
struct Harness {
    shared: Arc<Shared>, // observer only, not a logical owner
    thread: Option<JoinHandle<()>>,
}
fn start() -> (Owner, Harness) {
    let shared = Arc::new(Shared {
        state: Mutex::new(State { owners: 1, jobs: VecDeque::new(), waiting: false, ended: false }),
        ready: Condvar::new(),
        observed: Condvar::new(),
    });
    let worker = shared.clone();
    let thread = thread::spawn(move || {
        let mut s = worker.state.lock().unwrap();
        loop {
            if let Some(job) = s.jobs.pop_front() {
                drop(s);
                job();
                s = worker.state.lock().unwrap();
            } else if s.owners == 0 {
                s.ended = true;
                worker.observed.notify_all();
                return;
            } else {
                s.waiting = true;
                worker.observed.notify_all();
                s = worker.ready.wait(s).unwrap();
                s.waiting = false;
            }
        }
    });
    (Owner(shared.clone()), Harness { shared, thread: Some(thread) })
}
impl Harness {
    fn until(&self, predicate: impl Fn(&State) -> bool) {
        let s = self.shared.state.lock().unwrap();
        let (s, _) = self.shared.observed.wait_timeout_while(s, LIMIT, |s| !predicate(s)).unwrap();
        assert!(predicate(&s), "observer watchdog");
    }
    fn finish(mut self) {
        self.until(|s| s.ended);
        self.thread.take().unwrap().join().unwrap();
    }
}
fn report(owner: &Owner, tx: &mpsc::Sender<u32>, n: u32) {
    let tx = tx.clone();
    owner.submit(Box::new(move || tx.send(n).unwrap()));
}
#[test]
fn last_close_wakes_indefinite_idle_wait() {
    let (owner, h) = start();
    h.until(|s| s.waiting && s.owners == 1);
    drop(owner);
    h.finish();
}
#[test]
fn shared_owners_keep_worker_available() {
    let (owner, h) = start();
    let composite = owner.clone();
    let duplicate = composite.clone();
    drop(owner);
    drop(composite);
    h.until(|s| s.waiting && !s.ended && s.owners == 1);
    let (tx, rx) = mpsc::channel();
    report(&duplicate, &tx, 7);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 7);
    drop(duplicate);
    h.finish();
}
#[test]
fn delayed_owner_retains_port_until_delivery() {
    let (owner, h) = start();
    let delayed = owner.clone();
    let (release, gate) = mpsc::channel();
    let (tx, rx) = mpsc::channel();
    let delivery = thread::spawn(move || {
        gate.recv_timeout(LIMIT).unwrap();
        report(&delayed, &tx, 8);
        // Lease released only after submit.
    });
    drop(owner);
    h.until(|s| s.waiting && s.owners == 1 && !s.ended);
    release.send(()).unwrap();
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 8);
    delivery.join().unwrap();
    h.finish();
}
#[test]
fn last_close_during_blocked_callback_drains_fifo() {
    let (owner, h) = start();
    let (entered, entered_rx) = mpsc::channel();
    let (release, gate) = mpsc::channel();
    let (tx, rx) = mpsc::channel();
    let done = tx.clone();
    owner.submit(Box::new(move || {
        entered.send(()).unwrap();
        gate.recv_timeout(LIMIT).unwrap();
        done.send(1).unwrap();
    }));
    entered_rx.recv_timeout(LIMIT).unwrap();
    report(&owner, &tx, 2);
    report(&owner, &tx, 3);
    drop(owner);
    {
        let s = h.shared.state.lock().unwrap();
        assert_eq!((s.owners, s.jobs.len(), s.ended), (0, 2, false));
    }
    assert!(rx.try_recv().is_err());
    release.send(()).unwrap();
    for n in [1, 2, 3] { assert_eq!(rx.recv_timeout(LIMIT).unwrap(), n); }
    h.finish();
    assert!(rx.try_recv().is_err());
}
#[test]
fn reentrant_submission_and_last_owner_drop() {
    let (owner, h) = start();
    let nested = owner.clone();
    let (tx, rx) = mpsc::channel();
    owner.submit(Box::new(move || {
        report(&nested, &tx, 9);
        // Drops final lease inside callback, not under scheduler mutex.
    }));
    drop(owner);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 9);
    h.finish();
}
#[test]
fn empty_notification_does_not_end_owned_port() {
    let (owner, h) = start();
    h.until(|s| s.waiting);
    {
        let s = h.shared.state.lock().unwrap();
        assert_eq!(s.owners, 1);
        h.shared.ready.notify_one();
    }
    let (tx, rx) = mpsc::channel();
    report(&owner, &tx, 10);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 10);
    drop(owner);
    h.finish();
}
