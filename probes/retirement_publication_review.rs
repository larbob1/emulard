// SPDX-License-Identifier: GPL-3.0-or-later
//! Review-only model of host.rs retire/bury completion publication.
//! No actual runtime objects, fences, queues or GPU work.

use std::sync::{Arc, Mutex, atomic::{AtomicU64, Ordering}};

#[derive(Default)]
struct Ledger {
    started: AtomicU64,
    finished: AtomicU64,
    retired: Mutex<Vec<(u64, Sentinel)>>,
}

struct Sentinel(Arc<AtomicU64>);
impl Drop for Sentinel {
    fn drop(&mut self) { self.0.fetch_add(1, Ordering::SeqCst); }
}

impl Ledger {
    fn retire(&self, object: Sentinel, recheck: bool, before_lock: impl FnOnce()) {
        let started = self.started.load(Ordering::Acquire);
        if started <= self.finished.load(Ordering::Acquire) {
            drop(object);
            return;
        }
        // Deterministic pause at the existing gap before taking RETIRED.
        before_lock();
        let mut queue = self.retired.lock().unwrap();
        if recheck && started <= self.finished.load(Ordering::Acquire) {
            // Destruction must remain outside the retirement mutex.
            drop(queue);
            drop(object);
            return;
        }
        queue.push((started, object));
    }

    fn complete(&self, number: u64) {
        // Existing completion order: publish, then drain.
        self.finished.store(number, Ordering::Release);
        let done: Vec<_> = {
            let mut queue = self.retired.lock().unwrap();
            let (done, keep) = std::mem::take(&mut *queue).into_iter()
                .partition(|(at, _)| *at <= number);
            *queue = keep;
            done
        };
        drop(done);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;
    use std::time::Duration;
    const WAIT: Duration = Duration::from_secs(5);

    fn late_enqueue(recheck: bool, start_next: bool) {
        let ledger = Ledger::default();
        ledger.started.store(1, Ordering::Release);
        let drops = Arc::new(AtomicU64::new(0));
        let (paused, at_gap) = mpsc::channel();
        let (resume, proceed) = mpsc::channel();
        std::thread::scope(|scope| {
            let count = drops.clone();
            let state = &ledger;
            let worker = scope.spawn(move || state.retire(Sentinel(count), recheck, || {
                paused.send(()).unwrap();
                proceed.recv_timeout(WAIT).unwrap();
            }));
            at_gap.recv_timeout(WAIT).unwrap();
            assert_eq!(drops.load(Ordering::SeqCst), 0);
            ledger.complete(1);
            if start_next { ledger.started.store(2, Ordering::Release); }
            resume.send(()).unwrap();
            worker.join().unwrap();
        });
        assert_eq!(drops.load(Ordering::SeqCst), u64::from(recheck));
        assert_eq!(ledger.retired.lock().unwrap().len(), usize::from(!recheck));
        // Cleanup for the baseline delayed-drop counterexample.
        ledger.complete(if start_next { 2 } else { 1 });
        assert_eq!(drops.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn baseline_enqueue_after_drain_retains_object() {
        late_enqueue(false, false);
    }

    #[test]
    fn recheck_after_drain_drops_once() {
        late_enqueue(true, false);
    }

    #[test]
    fn captured_boundary_does_not_change_with_later_start() {
        // This only models objects whose last relevant submission is 1.
        // It does not prove that later recordings cannot use an object.
        late_enqueue(true, true);
    }

    #[test]
    fn incomplete_boundary_stays_retired_until_completion() {
        let ledger = Ledger::default();
        let drops = Arc::new(AtomicU64::new(0));
        ledger.started.store(2, Ordering::Release);
        for mode in [false, true] {
            ledger.retire(Sentinel(drops.clone()), mode, || {});
        }
        ledger.complete(1);
        assert_eq!(drops.load(Ordering::SeqCst), 0);
        assert_eq!(ledger.retired.lock().unwrap().len(), 2);
        ledger.complete(2);
        assert_eq!(drops.load(Ordering::SeqCst), 2);
        ledger.complete(2);
        assert_eq!(drops.load(Ordering::SeqCst), 2);
    }

    #[test]
    fn already_complete_never_enters_queue() {
        let ledger = Ledger::default();
        let drops = Arc::new(AtomicU64::new(0));
        for mode in [false, true] {
            ledger.retire(Sentinel(drops.clone()), mode, || panic!("unexpected slow path"));
        }
        assert_eq!(drops.load(Ordering::SeqCst), 2);
        assert!(ledger.retired.lock().unwrap().is_empty());
    }
}
