// Standalone host-thread model, not the actual victory-hle implementation.
use std::collections::VecDeque;
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

const LIMIT: Duration = Duration::from_secs(5);
type Job = Box<dyn FnOnce() + Send>;
#[derive(Default)]
struct State {
    tasks: VecDeque<(u32, Job)>,
    idle: usize,
    starting: usize,
    requested: usize,
    failed: usize,
    empty_wakes: usize,
    claimed: Vec<u32>,
    completed: Vec<u32>,
    closed: bool,
}
#[derive(Default)]
struct Shared {
    state: Mutex<State>,
    ready: Condvar,
    changed: Condvar,
}
struct Pool {
    reserve: bool,
    shared: Arc<Shared>,
    gates: Vec<Option<mpsc::Sender<()>>>,
    workers: Vec<JoinHandle<()>>,
}
fn worker(shared: Arc<Shared>, start: mpsc::Receiver<()>) {
    if start.recv().is_err() { return; }
    let mut s = shared.state.lock().unwrap();
    s.starting -= 1;
    shared.changed.notify_all();
    loop {
        while s.tasks.is_empty() && !s.closed {
            s.idle += 1;
            shared.changed.notify_all();
            s = shared.ready.wait(s).unwrap();
            s.idle -= 1;
            if s.tasks.is_empty() && !s.closed { s.empty_wakes += 1; }
        }
        if s.closed { return; }
        let (id, task) = s.tasks.pop_front().unwrap();
        s.claimed.push(id);
        shared.changed.notify_all();
        drop(s);
        task();
        s = shared.state.lock().unwrap();
        s.completed.push(id);
        shared.changed.notify_all();
    }
}
impl Pool {
    fn new(reserve: bool) -> Self {
        Self { reserve, shared: Arc::default(), gates: Vec::new(), workers: Vec::new() }
    }
    fn push_locked(&mut self, s: &mut State, id: u32, task: Job, fail: bool) -> bool {
        s.tasks.push_back((id, task));
        let capacity = s.idle + if self.reserve { s.starting } else { 0 };
        if s.tasks.len() > capacity {
            s.requested += 1;
            s.starting += 1;
            let (tx, rx) = mpsc::channel();
            let shared = self.shared.clone();
            // Failure injection, not an OS resource exhaustion test.
            let result = if fail { Err(std::io::Error::other("injected")) }
                else { thread::Builder::new().spawn(move || worker(shared, rx)) };
            match result {
                Ok(handle) => {
                    self.workers.push(handle);
                    self.gates.push(Some(tx));
                }
                Err(_) => {
                    s.starting -= 1;
                    s.failed += 1;
                    self.shared.ready.notify_one();
                    self.shared.changed.notify_all();
                    return false;
                }
            }
        } else {
            self.shared.ready.notify_one();
        }
        self.shared.changed.notify_all();
        true
    }
    fn submit(&mut self, id: u32, job: Job, fail: bool) -> bool {
        let shared = self.shared.clone();
        let mut s = shared.state.lock().unwrap();
        self.push_locked(&mut s, id, job, fail)
    }
    fn pair(&mut self, a: u32, b: u32) {
        // Force a scheduling interleaving; not a proposed runtime batch API.
        let shared = self.shared.clone();
        let mut s = shared.state.lock().unwrap();
        assert!(self.push_locked(&mut s, a, Box::new(|| {}), false));
        assert!(self.push_locked(&mut s, b, Box::new(|| {}), false));
    }
    fn start(&mut self, index: usize) {
        if let Some(gate) = self.gates[index].take() { gate.send(()).unwrap(); }
    }
    fn start_all(&mut self) {
        for i in 0..self.gates.len() { self.start(i); }
    }
    fn until(&self, predicate: impl Fn(&State) -> bool) {
        let deadline = Instant::now() + LIMIT;
        let mut s = self.shared.state.lock().unwrap();
        while !predicate(&s) {
            let remaining = deadline.saturating_duration_since(Instant::now());
            assert!(!remaining.is_zero(), "fixture deadline");
            s = self.shared.changed.wait_timeout(s, remaining).unwrap().0;
        }
    }
    fn inspect<R>(&self, read: impl FnOnce(&State) -> R) -> R {
        read(&self.shared.state.lock().unwrap())
    }
    fn plain(&mut self, id: u32) {
        assert!(self.submit(id, Box::new(|| {}), false));
    }
}
impl Drop for Pool {
    fn drop(&mut self) {
        {
            let mut s = self.shared.state.lock().unwrap_or_else(|e| e.into_inner());
            s.closed = true;
            self.shared.ready.notify_all();
        }
        // Release any gated worker; no queued callbacks execute after close.
        for gate in self.gates.iter_mut().filter_map(Option::take) { let _ = gate.send(()); }
        for handle in self.workers.drain(..) {
            let _ = handle.join();
        }
    }
}
fn completed(p: &Pool, expected: &[u32]) {
    p.until(|s| s.completed.len() == expected.len());
    p.inspect(|s| {
        assert_eq!(s.claimed.as_slice(), expected);
        let mut done = s.completed.clone();
        done.sort_unstable();
        assert_eq!(done.as_slice(), expected);
    });
}
#[test]
fn drains_before_pending_worker_starts() {
    for (reserve, requests) in [(false, 3), (true, 2)] {
        let mut p = Pool::new(reserve);
        p.pair(1, 2);
        p.start(0);
        p.until(|s| s.completed.len() == 2 && s.idle == 1 && s.starting == 1);
        p.pair(3, 4);
        assert_eq!(p.inspect(|s| s.requested), requests);
        p.start_all();
        completed(&p, &[1, 2, 3, 4]);
    }
}
#[test]
fn blocked_callback_does_not_count_as_available_worker() {
    for reserve in [false, true] {
        let mut p = Pool::new(reserve);
        let (entered_tx, entered_rx) = mpsc::channel();
        let (done_tx, done_rx) = mpsc::channel();
        assert!(p.submit(1, Box::new(move || {
            entered_tx.send(()).unwrap();
            done_rx.recv_timeout(LIMIT).expect("blocked callback starved");
        }), false));
        p.start(0);
        entered_rx.recv_timeout(LIMIT).unwrap();
        assert!(p.submit(2, Box::new(move || { done_tx.send(()).unwrap(); }), false));
        assert_eq!(p.inspect(|s| s.requested), 2);
        p.start(1);
        completed(&p, &[1, 2]);
    }
}
#[test]
fn empty_notification_rechecks_predicate() {
    for reserve in [false, true] {
        let mut p = Pool::new(reserve);
        p.plain(1);
        p.start(0);
        p.until(|s| s.idle == 1);
        { let _guard = p.shared.state.lock().unwrap(); p.shared.ready.notify_all(); }
        p.until(|s| s.empty_wakes >= 1 && s.idle == 1);
        assert_eq!(p.inspect(|s| s.claimed.clone()), vec![1]);
        p.plain(2);
        completed(&p, &[1, 2]);
        assert_eq!(p.inspect(|s| s.requested), 1);
    }
}
#[test]
fn failure_rolls_back_pending_reservation() {
    for reserve in [false, true] {
        let mut p = Pool::new(reserve);
        assert!(!p.submit(1, Box::new(|| {}), true));
        assert_eq!(p.inspect(|s| (s.starting, s.failed)), (0, 1));
        // Fixture-only recovery on next submit; not an API error policy.
        p.plain(2);
        p.start(0);
        completed(&p, &[1, 2]);
        assert_eq!(p.inspect(|s| s.requested), 2);
    }
}
#[test]
fn reserved_capacity_depends_on_pending_start() {
    let mut p = Pool::new(true);
    p.pair(1, 2);
    p.start(0);
    p.until(|s| s.completed.len() == 2 && s.idle == 1 && s.starting == 1);
    let (entered_tx, entered_rx) = mpsc::channel();
    let (done_tx, done_rx) = mpsc::channel();
    {
        let shared = p.shared.clone();
        let mut s = shared.state.lock().unwrap();
        assert!(p.push_locked(&mut s, 3, Box::new(move || {
            entered_tx.send(()).unwrap();
            done_rx.recv_timeout(LIMIT).expect("pending start never ran");
        }), false));
        assert!(p.push_locked(&mut s, 4, Box::new(move || { done_tx.send(()).unwrap(); }), false));
    }
    entered_rx.recv_timeout(LIMIT).unwrap();
    // Sole active worker waits for queued job, which depends on pending start.
    assert_eq!(p.inspect(|s| (s.starting, s.idle, s.tasks.len(), s.requested)), (1, 0, 1, 2));
    p.start(1);
    completed(&p, &[1, 2, 3, 4]);
}
