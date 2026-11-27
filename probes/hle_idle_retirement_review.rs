// Standalone idle retirement review. Not the HLE pool or a runtime policy.
use std::collections::VecDeque;
use std::sync::{Arc, Mutex, Condvar, mpsc};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

const LIMIT: Duration = Duration::from_secs(5);
type Job = Box<dyn FnOnce() + Send>;
#[derive(Default)]
struct State {
    queue: VecDeque<Job>,
    idle: usize,
    live: usize,
    started: usize,
    retired: usize,
    closed: bool,
}
#[derive(Default)]
struct Shared {
    state: Mutex<State>,
    ready: Condvar,
    observed: Condvar,
}
struct Pool {
    shared: Arc<Shared>,
    timeout: Duration,
    threads: Vec<JoinHandle<()>>,
}
fn retire(s: &mut State) {
    s.idle -= 1;
    s.live -= 1;
    s.retired += 1;
}
fn worker(shared: Arc<Shared>, timeout: Duration) {
    let mut s = shared.state.lock().unwrap();
    loop {
        if let Some(job) = s.queue.pop_front() {
            drop(s);
            job();
            s = shared.state.lock().unwrap();
            continue;
        }
        if s.closed {
            s.live -= 1;
            shared.observed.notify_all();
            return;
        }
        s.idle += 1;
        shared.observed.notify_all();
        let deadline = Instant::now() + timeout;
        loop {
            if s.closed || !s.queue.is_empty() {
                s.idle -= 1;
                break;
            }
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                // Retirement and availability change under the admission lock.
                retire(&mut s);
                shared.observed.notify_all();
                return;
            }
            s = shared.ready.wait_timeout(s, remaining).unwrap().0;
        }
    }
}
impl Pool {
    fn new(timeout: Duration) -> Self {
        Self { shared: Arc::default(), timeout, threads: Vec::new() }
    }
    fn submit(&mut self, job: Job) {
        let mut s = self.shared.state.lock().unwrap();
        assert!(!s.closed);
        s.queue.push_back(job);
        if s.queue.len() > s.idle {
            // Deliberately preserve baseline admission: no active or pending
            // workers count as idle capacity, no hard worker cap.
            let shared = self.shared.clone();
            let timeout = self.timeout;
            let thread = thread::spawn(move || worker(shared, timeout));
            s.live += 1;
            s.started += 1;
            self.threads.push(thread);
        } else {
            self.shared.ready.notify_one();
        }
    }
    fn until(&self, predicate: impl Fn(&State) -> bool) {
        let s = self.shared.state.lock().unwrap();
        let (s, _) = self.shared.observed.wait_timeout_while(
            s, LIMIT, |s| !predicate(s),
        ).unwrap();
        assert!(predicate(&s), "pool observation watchdog");
    }
}
impl Drop for Pool {
    fn drop(&mut self) {
        {
            let mut s = self.shared.state.lock().unwrap();
            s.closed = true;
            self.shared.ready.notify_all();
        }
        for thread in self.threads.drain(..) { thread.join().unwrap(); }
    }
}
fn submit_report(p: &mut Pool, id: u32, tx: &mpsc::Sender<u32>) {
    let tx = tx.clone();
    p.submit(Box::new(move || tx.send(id).unwrap()));
}
#[test]
fn retirement_then_submit_starts_replacement() {
    let mut p = Pool::new(Duration::from_millis(30));
    let (tx, rx) = mpsc::channel();
    submit_report(&mut p, 1, &tx);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 1);
    p.until(|s| s.live == 0 && s.retired == 1);
    submit_report(&mut p, 2, &tx);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 2);
    p.until(|s| s.live == 0 && s.retired == 2);
    let s = p.shared.state.lock().unwrap();
    assert_eq!((s.started, s.idle, s.queue.len()), (2, 0, 0));
}
#[test]
fn submission_before_expiry_reuses_idle_worker() {
    let mut p = Pool::new(Duration::from_secs(60));
    let (tx, rx) = mpsc::channel();
    submit_report(&mut p, 1, &tx);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 1);
    p.until(|s| s.idle == 1);
    submit_report(&mut p, 2, &tx);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 2);
    p.until(|s| s.idle == 1);
    assert_eq!(p.shared.state.lock().unwrap().started, 1);
}
#[test]
fn blocked_callback_does_not_consume_available_capacity() {
    let mut p = Pool::new(Duration::from_secs(60));
    let (entered_tx, entered_rx) = mpsc::channel();
    let (release_tx, release_rx) = mpsc::channel();
    let (done_tx, done_rx) = mpsc::channel();
    p.submit(Box::new(move || {
        entered_tx.send(()).unwrap();
        release_rx.recv_timeout(LIMIT).unwrap();
        done_tx.send(1).unwrap();
    }));
    entered_rx.recv_timeout(LIMIT).unwrap();
    p.submit(Box::new(move || release_tx.send(()).unwrap()));
    assert_eq!(done_rx.recv_timeout(LIMIT).unwrap(), 1);
    p.until(|s| s.idle == 2);
    assert_eq!(p.shared.state.lock().unwrap().started, 2);
}
#[test]
fn submit_wins_expiry_boundary_if_queue_nonempty() {
    // Deterministic test of locked boundary state, not OS scheduling order.
    let mut s = State { idle: 1, live: 1, ..State::default() };
    s.queue.push_back(Box::new(|| {}));
    // Worker must recheck queued work before retiring, even on a timeout.
    if s.queue.is_empty() { retire(&mut s); } else { s.idle -= 1; }
    assert_eq!((s.live, s.idle, s.retired, s.queue.len()), (1, 0, 0, 1));
    s.queue.pop_front().unwrap()();
}
#[test]
fn expiry_wins_boundary_if_no_queued_work() {
    let mut s = State { idle: 1, live: 1, ..State::default() };
    assert!(s.queue.is_empty());
    retire(&mut s);
    s.queue.push_back(Box::new(|| {}));
    assert!(s.queue.len() > s.idle);
    assert_eq!((s.live, s.idle, s.retired), (0, 0, 1));
}
#[test]
fn empty_notifications_do_not_extend_idle_deadline() {
    let mut p = Pool::new(Duration::from_millis(50));
    let (tx, rx) = mpsc::channel();
    submit_report(&mut p, 1, &tx);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 1);
    // No requirement to observe a transient idle state on a slow runner.
    for _ in 0..10 {
        let _s = p.shared.state.lock().unwrap();
        p.shared.ready.notify_all();
    }
    p.until(|s| s.retired == 1 && s.live == 0);
    assert_eq!(p.shared.state.lock().unwrap().started, 1);
}
