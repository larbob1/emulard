// SPDX-License-Identifier: GPL-3.0-or-later
//! Standalone worker-idle trim review with real Mutex/Condvar.
//! Not the runtime scheduler: fixed head order, synthetic staging and
//! explicit test gates. Wait timeouts are watchdogs, not a proposed policy.

use std::collections::VecDeque;
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

const DEADLINE: Duration = Duration::from_secs(5);
type Job = (u32, u64);

#[derive(Default)]
struct State {
    pending: VecDeque<Job>,
    staged: u64,
    limit: u64,
    starved: bool,
    refused: usize,
    stopped: bool,
    wake_epoch: u32,
}

impl State {
    // Same staging refusal rule as the pinned scheduler. Fixed synthetic
    // head order deliberately omits real class/lane virtual clocks.
    fn start(&mut self) -> Option<Job> {
        let job = *self.pending.front()?;
        if self.staged > 0 && self.staged + job.1 > self.limit {
            self.starved = true;
            self.refused += 1;
            return None;
        }
        self.pending.pop_front();
        self.staged += job.1;
        Some(job)
    }
}

#[derive(Default)]
struct Shared {
    state: Mutex<State>,
    work: Condvar,
    finished: Condvar,
}

#[derive(Debug, PartialEq, Eq)]
enum Event { Trimmed, Waiting(u32) }

#[derive(Debug, PartialEq, Eq)]
struct Report {
    job: Option<Job>,
    trims: usize,
    waits: usize,
    attempts: usize,
    retained: usize,
}

struct Worker {
    events: mpsc::Receiver<Event>,
    release: mpsc::Sender<()>,
    join: JoinHandle<Report>,
}

impl Worker {
    fn expect(&self, event: Event) {
        assert_eq!(self.events.recv_timeout(DEADLINE).unwrap(), event);
    }

    fn wait_epoch(&self, expected: u32) {
        let deadline = Instant::now() + DEADLINE;
        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            assert!(!remaining.is_zero(), "wait epoch watchdog");
            match self.events.recv_timeout(remaining).unwrap() {
                Event::Waiting(epoch) if epoch == expected => return,
                Event::Waiting(epoch) if epoch < expected => continue,
                other => panic!("unexpected wait epoch: {other:?}"),
            }
        }
    }

    fn finish(self) -> Report {
        self.join.join().unwrap()
    }
}

fn spawn(shared: Arc<Shared>, idle: Vec<u8>) -> Worker {
    let (events, recv) = mpsc::channel();
    let (release, gate) = mpsc::channel();
    let join = thread::spawn(move || {
        let mut idle = idle;
        let mut report = Report {
            job: None, trims: 0, waits: 0, attempts: 0, retained: 0,
        };
        let mut state = shared.state.lock().unwrap();
        loop {
            if state.stopped { break; }
            report.attempts += 1;
            if let Some(job) = state.start() {
                report.job = Some(job);
                break;
            }
            if idle.capacity() != 0 {
                // Do not free while holding the scheduler mutex. A
                // notification can arrive during this unlocked interval.
                drop(state);
                drop(std::mem::take(&mut idle));
                report.trims += 1;
                events.send(Event::Trimmed).unwrap();
                // Test-only explicit gate AFTER actual Vec release.
                gate.recv_timeout(DEADLINE).expect("trim release watchdog");
                state = shared.state.lock().unwrap();
                // Crucial: recheck selection under the mutex before wait.
                // A previous work notification is not a stored permit.
                continue;
            }
            report.waits += 1;
            events.send(Event::Waiting(state.wake_epoch)).unwrap();
            // The timeout exists solely to bound this test if progress
            // fails. No periodic wait or timeout-driven trimming proposed.
            let (next, timeout) = shared.work.wait_timeout(state, DEADLINE).unwrap();
            assert!(!timeout.timed_out(), "work wait watchdog");
            state = next;
        }
        report.retained = idle.capacity();
        drop(state);
        report
    });
    Worker { events: recv, release, join }
}

fn setup(staged: u64, jobs: &[Job]) -> Arc<Shared> {
    Arc::new(Shared {
        state: Mutex::new(State {
            pending: jobs.iter().copied().collect(),
            staged, limit: 100, ..State::default()
        }),
        ..Shared::default()
    })
}

#[test]
fn submit_during_trim_is_seen_without_waiting() {
    let shared = setup(0, &[]);
    let worker = spawn(shared.clone(), vec![0; 4096]);
    worker.expect(Event::Trimmed);
    // Obtaining the lock here proves the worker has released it at the
    // controlled trim boundary. Notification occurs before its recheck.
    {
        let mut state = shared.state.lock().unwrap();
        state.pending.push_back((1, 16));
        shared.work.notify_all();
    }
    worker.release.send(()).unwrap();
    assert_eq!(worker.finish(), Report {
        job: Some((1, 16)), trims: 1, waits: 0, attempts: 2, retained: 0,
    });
}

#[test]
fn refused_head_stays_first_across_trim_and_wake() {
    let shared = setup(60, &[(1, 500), (2, 0)]);
    let worker = spawn(shared.clone(), vec![0; 4096]);
    worker.expect(Event::Trimmed);
    {
        let state = shared.state.lock().unwrap();
        assert_eq!(state.pending.front(), Some(&(1, 500)));
        assert!(state.starved);
        assert_eq!(state.refused, 1);
    }
    worker.release.send(()).unwrap();
    worker.wait_epoch(0);
    {
        let mut state = shared.state.lock().unwrap();
        assert_eq!(state.pending.len(), 2);
        // Recheck really is a second attempt: do not claim refusal
        // counters remain identical to an implementation without trim.
        assert!(state.refused >= 2);
        state.staged = 0;
        assert!(std::mem::take(&mut state.starved));
        shared.work.notify_all();
        shared.finished.notify_all();
    }
    let report = worker.finish();
    assert_eq!(report.job, Some((1, 500)));
    assert_eq!(report.trims, 1);
    assert!(report.waits >= 1);
    assert_eq!(report.attempts, report.waits + 2);
    let state = shared.state.lock().unwrap();
    assert_eq!(state.staged, 500);
    assert_eq!(state.pending.front(), Some(&(2, 0)));
}

#[test]
fn completion_during_trim_is_seen_before_wait() {
    let shared = setup(60, &[(1, 500)]);
    let worker = spawn(shared.clone(), vec![0; 4096]);
    worker.expect(Event::Trimmed);
    {
        let mut state = shared.state.lock().unwrap();
        state.staged = 0;
        assert!(std::mem::take(&mut state.starved));
        shared.work.notify_all();
        shared.finished.notify_all();
    }
    worker.release.send(()).unwrap();
    let report = worker.finish();
    assert_eq!(report.job, Some((1, 500)));
    assert_eq!((report.trims, report.waits, report.attempts), (1, 0, 2));
}

#[test]
fn empty_wake_does_not_trim_twice_or_skip_wait() {
    let shared = setup(0, &[]);
    let worker = spawn(shared.clone(), vec![0; 4096]);
    worker.expect(Event::Trimmed);
    worker.release.send(()).unwrap();
    worker.wait_epoch(0);
    {
        let mut state = shared.state.lock().unwrap();
        state.wake_epoch = 1;
        shared.work.notify_all();
    }
    worker.wait_epoch(1);
    {
        let mut state = shared.state.lock().unwrap();
        state.stopped = true;
        shared.work.notify_all();
    }
    let report = worker.finish();
    assert_eq!(report.job, None);
    assert_eq!((report.trims, report.retained), (1, 0));
    assert!(report.waits >= 2);
    assert_eq!(report.attempts, report.waits + 1);
}

#[test]
fn no_retained_capacity_waits_without_trim() {
    let shared = setup(0, &[]);
    let worker = spawn(shared.clone(), Vec::new());
    worker.wait_epoch(0);
    {
        let mut state = shared.state.lock().unwrap();
        state.pending.push_back((7, 0));
        shared.work.notify_all();
    }
    let report = worker.finish();
    assert_eq!(report.job, Some((7, 0)));
    assert_eq!((report.trims, report.retained), (0, 0));
    assert!(report.waits >= 1);
    assert_eq!(report.attempts, report.waits + 1);
}

#[test]
fn immediate_work_does_not_trim() {
    let shared = setup(0, &[(9, 1)]);
    let worker = spawn(shared, vec![0; 4096]);
    assert_eq!(worker.finish(), Report {
        job: Some((9, 1)), trims: 0, waits: 0, attempts: 1, retained: 4096,
    });
}
