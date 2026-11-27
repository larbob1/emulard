// Standalone ownership model, not actual HLE or a production patch.
use std::collections::VecDeque;
use std::sync::{Arc, Condvar, Mutex, Weak, mpsc};
use std::thread::{self, JoinHandle};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

const LIMIT: Duration = Duration::from_secs(5);
type Job = Box<dyn FnOnce() + Send>;
type Task = Box<dyn FnOnce(bool) + Send>;
struct State {
    jobs: VecDeque<Task>,
    closed: bool,
    wait_epoch: usize,
    ended: bool,
}
struct WorkerState {
    state: Mutex<State>,
    ready: Condvar,
    observed: Condvar,
}
struct Port {
    worker: Arc<WorkerState>,
}
struct Queue {
    ports: [Arc<Port>; 2],
    terminated: AtomicBool,
}
impl Drop for Port {
    fn drop(&mut self) {
        let mut s = self.worker.state.lock().unwrap();
        assert!(!s.closed);
        s.closed = true;
        self.worker.ready.notify_one();
        // No callbacks, join, process-queue acquisition, or worker-state drop
        // under this lock. The worker still owns its independent state.
    }
}
impl Port {
    fn submit(&self, job: Task) {
        let mut s = self.worker.state.lock().unwrap();
        assert!(!s.closed);
        s.jobs.push_back(job);
        self.worker.ready.notify_one();
    }
}
impl Queue {
    fn new(work: Arc<Port>, completion: Arc<Port>) -> Arc<Self> {
        Arc::new(Self { ports: [work, completion], terminated: AtomicBool::new(false) })
    }
    fn composite(source: &Self) -> Arc<Self> {
        Self::new(source.ports[0].clone(), source.ports[1].clone())
    }
    fn submit(&self, slot: usize, job: Job) {
        assert!(self.submit_task(slot, Box::new(move |canceled| {
            assert!(!canceled);
            job();
        })));
    }
    fn submit_task(&self, slot: usize, task: Task) -> bool {
        if self.terminated.load(Ordering::Acquire) { return false; }
        self.deliver(slot, task);
        true
    }
    fn deliver(&self, slot: usize, task: Task) {
        // Already accepted delayed work uses this path, without a second
        // termination check, matching the pinned source's behavior.
        self.ports[slot].submit(task);
    }
    fn terminate(&self) {
        self.terminated.store(true, Ordering::Release);
        // Preserve each slot's distinct drain, even if both alias one port.
        for port in &self.ports {
            let pending: Vec<_> = port.worker.state.lock().unwrap().jobs.drain(..).collect();
            port.worker.ready.notify_all();
            for task in pending { task(true); }
        }
    }
}
struct Harness {
    worker: Arc<WorkerState>, // observer retains state, not Port
    port: Weak<Port>,
    thread: JoinHandle<()>,
}
fn start() -> (Arc<Queue>, Harness) {
    let worker = Arc::new(WorkerState {
        state: Mutex::new(State { jobs: VecDeque::new(), closed: false,
                                  wait_epoch: 0, ended: false }),
        ready: Condvar::new(),
        observed: Condvar::new(),
    });
    let port = Arc::new(Port { worker: worker.clone() });
    let weak = Arc::downgrade(&port);
    let queue = Queue::new(port.clone(), port);
    let shared = worker.clone();
    let thread = thread::spawn(move || {
        let mut s = shared.state.lock().unwrap();
        loop {
            if let Some(job) = s.jobs.pop_front() {
                drop(s);
                job(false);
                s = shared.state.lock().unwrap();
            } else if s.closed {
                s.ended = true;
                shared.observed.notify_all();
                return;
            } else {
                s.wait_epoch = s.wait_epoch.checked_add(1).unwrap();
                shared.observed.notify_all();
                s = shared.ready.wait(s).unwrap();
            }
        }
    });
    (queue, Harness { worker, port: weak, thread })
}
impl Harness {
    fn until(&self, predicate: impl Fn(&State) -> bool) {
        let s = self.worker.state.lock().unwrap();
        let (s, _) = self.worker.observed.wait_timeout_while(
            s, LIMIT, |s| !predicate(s)).unwrap();
        assert!(predicate(&s), "observer watchdog");
    }
    fn finish(self) {
        self.until(|s| s.ended && s.closed && s.jobs.is_empty());
        assert!(self.port.upgrade().is_none());
        self.thread.join().unwrap();
        assert_eq!(Arc::strong_count(&self.worker), 1);
    }
}
fn report(q: &Queue, slot: usize, tx: &mpsc::Sender<u32>, id: u32) {
    let tx = tx.clone();
    q.submit(slot, Box::new(move || tx.send(id).unwrap()));
}
#[test]
fn final_idle_close_releases_port_and_worker() {
    let (q, h) = start();
    h.until(|s| s.wait_epoch > 0);
    drop(q);
    h.finish();
}
#[test]
fn duplicate_queue_does_not_duplicate_port_slots() {
    let (q, h) = start();
    assert!(Arc::ptr_eq(&q.ports[0], &q.ports[1]));
    assert_eq!(h.port.strong_count(), 2);
    let duplicate = q.clone();
    assert_eq!(h.port.strong_count(), 2);
    let composite = Queue::composite(&q);
    assert_eq!(h.port.strong_count(), 4);
    drop(q);
    assert_eq!(h.port.strong_count(), 4);
    drop(duplicate);
    assert_eq!(h.port.strong_count(), 2);
    let (tx, rx) = mpsc::channel();
    report(&composite, 0, &tx, 1);
    report(&composite, 1, &tx, 2);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 1);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 2);
    drop(composite);
    h.finish();
}
#[test]
fn delayed_queue_owns_port_until_delivery() {
    let (q, h) = start();
    let retained = q.clone();
    let (release, gate) = mpsc::channel();
    let (tx, rx) = mpsc::channel();
    let delayed = thread::spawn(move || {
        gate.recv_timeout(LIMIT).unwrap();
        report(&retained, 0, &tx, 3);
        // Final queue reference is dropped after submission.
    });
    drop(q);
    h.until(|s| s.wait_epoch > 0 && !s.closed);
    assert_eq!(h.port.strong_count(), 2);
    release.send(()).unwrap();
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 3);
    delayed.join().unwrap();
    h.finish();
}
#[test]
fn process_queue_retains_port_and_clear_does_not_join() {
    let (q, h) = start();
    let process = Arc::new(Mutex::new(Some(q.clone())));
    let process_cb = process.clone();
    let (entered, entered_rx) = mpsc::channel();
    let (release, gate) = mpsc::channel();
    let (done, done_rx) = mpsc::channel();
    q.submit(0, Box::new(move || {
        entered.send(()).unwrap();
        gate.recv_timeout(LIMIT).unwrap();
        // A callback may need the process queue mutex.
        assert!(process_cb.lock().unwrap().is_none());
        done.send(()).unwrap();
    }));
    entered_rx.recv_timeout(LIMIT).unwrap();
    drop(q);
    assert_eq!(h.port.strong_count(), 2);
    {
        let mut p = process.lock().unwrap();
        // Drop the final queue while this mutex is held.
        // No join or callback in Port::drop.
        *p = None;
        assert!(h.port.upgrade().is_none());
        assert!(done_rx.try_recv().is_err());
    }
    release.send(()).unwrap();
    done_rx.recv_timeout(LIMIT).unwrap();
    h.finish();
}
#[test]
fn last_close_during_callback_drains_accepted_jobs() {
    let (q, h) = start();
    let (entered, entered_rx) = mpsc::channel();
    let (release, gate) = mpsc::channel();
    let (tx, rx) = mpsc::channel();
    let done = tx.clone();
    q.submit(0, Box::new(move || {
        entered.send(()).unwrap();
        gate.recv_timeout(LIMIT).unwrap();
        done.send(4).unwrap();
    }));
    entered_rx.recv_timeout(LIMIT).unwrap();
    report(&q, 0, &tx, 5);
    report(&q, 1, &tx, 6);
    drop(q);
    assert!(h.port.upgrade().is_none());
    {
        let s = h.worker.state.lock().unwrap();
        assert!(s.closed && !s.ended);
        assert_eq!(s.jobs.len(), 2);
    }
    release.send(()).unwrap();
    for id in [4, 5, 6] {
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), id);
    }
    h.finish();
    assert!(rx.try_recv().is_err());
}
#[test]
fn reentrant_submission_then_final_queue_drop() {
    let (q, h) = start();
    let nested = q.clone();
    let (tx, rx) = mpsc::channel();
    q.submit(0, Box::new(move || {
        report(&nested, 1, &tx, 7);
        // Callback drops the retained queue outside task-state mutex.
    }));
    drop(q);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 7);
    h.finish();
}
#[test]
fn empty_notification_rechecks_before_submission() {
    let (q, h) = start();
    h.until(|s| s.wait_epoch > 0);
    let initial = {
        let s = h.worker.state.lock().unwrap();
        assert!(s.jobs.is_empty() && !s.closed && !s.ended);
        h.worker.ready.notify_one();
        s.wait_epoch
    };
    // Observe a subsequent empty predicate and wait under same mutex.
    // Not a count of OS wakeups: spurious wakes are permitted.
    h.until(|s| s.wait_epoch > initial && s.jobs.is_empty() && !s.closed && !s.ended);
    let (tx, rx) = mpsc::channel();
    report(&q, 0, &tx, 8);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 8);
    drop(q);
    h.finish();
}

fn report_task(tx: &mpsc::Sender<(u32, bool)>, id: u32) -> Task {
    let tx = tx.clone();
    Box::new(move |canceled| tx.send((id, canceled)).unwrap())
}

// Characterize the current shared-drain behavior, not an API conformance claim.
#[test]
fn termination_drains_shared_queue_without_closing_survivor() {
    let (q, h) = start();
    let other = Queue::composite(&q);
    let (entered, entered_rx) = mpsc::channel();
    let (release, gate) = mpsc::channel();
    let (tx, rx) = mpsc::channel();
    let active = tx.clone();
    assert!(q.submit_task(0, Box::new(move |canceled| {
        entered.send(()).unwrap();
        gate.recv_timeout(LIMIT).unwrap();
        active.send((1, canceled)).unwrap();
    })));
    entered_rx.recv_timeout(LIMIT).unwrap();
    assert!(q.submit_task(0, report_task(&tx, 2)));
    assert!(other.submit_task(1, report_task(&tx, 3)));
    q.terminate();
    // Both were queued on the shared port, including other queue's work.
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (2, true));
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (3, true));
    assert!(!q.submit_task(0, report_task(&tx, 4)));
    assert!(other.submit_task(0, report_task(&tx, 5)));
    drop(q);
    assert!(!h.worker.state.lock().unwrap().closed);
    release.send(()).unwrap();
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (1, false));
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (5, false));
    drop(other);
    h.finish();
    assert!(rx.try_recv().is_err());
}

#[test]
fn second_aliased_slot_drains_reentrant_submission() {
    let (q, h) = start();
    let other = Queue::composite(&q);
    let (entered, entered_rx) = mpsc::channel();
    let (release, gate) = mpsc::channel();
    let (tx, rx) = mpsc::channel();
    let active = tx.clone();
    assert!(q.submit_task(0, Box::new(move |canceled| {
        entered.send(()).unwrap();
        gate.recv_timeout(LIMIT).unwrap();
        active.send((1, canceled)).unwrap();
    })));
    entered_rx.recv_timeout(LIMIT).unwrap();
    let reentrant = other.clone();
    let callback_tx = tx.clone();
    assert!(q.submit_task(0, Box::new(move |canceled| {
        callback_tx.send((2, canceled)).unwrap();
        assert!(reentrant.submit_task(0, report_task(&callback_tx, 3)));
    })));
    // First slot drains callback 2. Its reentrant submission to the open
    // composite is drained by the second slot while worker remains gated.
    q.terminate();
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (2, true));
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (3, true));
    assert!(other.submit_task(1, report_task(&tx, 4)));
    release.send(()).unwrap();
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (1, false));
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (4, false));
    drop(q);
    drop(other);
    h.finish();
    assert!(rx.try_recv().is_err());
}

#[test]
fn accepted_delayed_delivery_survives_queue_termination_and_close() {
    let (q, h) = start();
    let (release, gate) = mpsc::channel();
    let (tx, rx) = mpsc::channel();
    let retained = q.clone();
    // Model the initial acceptance check and retained delayed closure.
    assert!(!q.terminated.load(Ordering::Acquire));
    let delayed = thread::spawn(move || {
        gate.recv_timeout(LIMIT).unwrap();
        retained.deliver(0, report_task(&tx, 6));
    });
    q.terminate();
    let (rejected_tx, rejected_rx) = mpsc::channel();
    assert!(!q.submit_task(0, report_task(&rejected_tx, 7)));
    drop(q);
    assert_eq!(h.port.strong_count(), 2);
    assert!(!h.worker.state.lock().unwrap().closed);
    release.send(()).unwrap();
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (6, false));
    delayed.join().unwrap();
    h.finish();
    assert!(rejected_rx.try_recv().is_err());
    assert!(rx.try_recv().is_err());
}
