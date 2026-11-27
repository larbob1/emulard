// Review-only std model. No D3D, shader translation, runtime queue, or FFI.
// Source finding: rorodev6/victory-nvidia-megafork b5fc03002ef4ce7a8804322994b742afe0661980.
// Independently authored model; not a proposed production unwind boundary.
#[cfg(test)]
mod tests {
    use std::panic::{catch_unwind, AssertUnwindSafe};
    use std::sync::{Arc, Condvar, Mutex, OnceLock, Barrier, mpsc};
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::time::Duration;

    const LIMIT: Duration = Duration::from_secs(5);

    #[derive(Default)]
    struct Pending {
        made: OnceLock<Option<u32>>,
        done: (Mutex<()>, Condvar),
    }

    impl Pending {
        fn make(&self, build: impl FnOnce() -> Option<u32>) {
            self.made.get_or_init(|| {
                // Only known synthetic string panics in these tests.
                // Real compiler/driver/cache state and payload destructors
                // need independent review before any analogous runtime port.
                catch_unwind(AssertUnwindSafe(build)).unwrap_or(None)
            });
            let (lock, done) = &self.done;
            let _held = lock.lock().unwrap();
            done.notify_all();
        }

        fn wait(&self, entered: mpsc::Sender<()>) -> Option<Option<u32>> {
            let (lock, done) = &self.done;
            let held = lock.lock().unwrap();
            entered.send(()).unwrap();
            let (_held, _) = done.wait_timeout_while(held, LIMIT,
                |_| self.made.get().is_none()).unwrap();
            self.made.get().copied()
        }
    }

    #[test]
    fn baseline_unwind_leaves_cell_unpublished_and_accounting_unreached() {
        let made = OnceLock::<Option<u32>>::new();
        let waiting = AtomicUsize::new(1);
        let result = catch_unwind(|| {
            made.get_or_init(|| panic!("synthetic build"));
            waiting.fetch_sub(1, Ordering::Relaxed);
        });
        assert!(result.is_err());
        assert_eq!(made.get(), None);
        assert_eq!(waiting.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn terminal_refusal_wakes_waiters_and_is_not_rebuilt() {
        let p = Arc::new(Pending::default());
        let (entered_tx, entered_rx) = mpsc::channel();
        let (result_tx, result_rx) = mpsc::channel();
        let mut threads = Vec::new();
        for _ in 0..2 {
            let p = p.clone();
            let entered = entered_tx.clone();
            let result = result_tx.clone();
            threads.push(std::thread::spawn(move || {
                result.send(p.wait(entered)).unwrap();
            }));
        }
        for _ in 0..2 { entered_rx.recv_timeout(LIMIT).unwrap(); }
        p.make(|| panic!("synthetic build"));
        for _ in 0..2 {
            assert_eq!(result_rx.recv_timeout(LIMIT).unwrap(), Some(None));
        }
        for thread in threads { thread.join().unwrap(); }
        let attempts = AtomicUsize::new(0);
        p.make(|| {
            attempts.fetch_add(1, Ordering::Relaxed);
            Some(123)
        });
        assert_eq!(attempts.load(Ordering::Relaxed), 0);
        assert_eq!(p.made.get(), Some(&None));
    }

    #[test]
    fn completion_before_wait_is_visible() {
        let p = Pending::default();
        p.make(|| Some(42));
        let (entered, receipt) = mpsc::channel();
        assert_eq!(p.wait(entered), Some(Some(42)));
        receipt.recv_timeout(LIMIT).unwrap();
    }

    #[test]
    fn competing_callers_initialize_once() {
        let p = Arc::new(Pending::default());
        let attempts = Arc::new(AtomicUsize::new(0));
        let start = Arc::new(Barrier::new(3));
        let (tx, rx) = mpsc::channel();
        let mut threads = Vec::new();
        for value in [17u32, 29] {
            let (p, attempts, start, tx) =
                (p.clone(), attempts.clone(), start.clone(), tx.clone());
            threads.push(std::thread::spawn(move || {
                start.wait();
                p.make(|| {
                    attempts.fetch_add(1, Ordering::Relaxed);
                    Some(value)
                });
                tx.send(*p.made.get().unwrap()).unwrap();
            }));
        }
        start.wait();
        let first = rx.recv_timeout(LIMIT).unwrap();
        assert!(matches!(first, Some(17 | 29)));
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), first);
        for thread in threads { thread.join().unwrap(); }
        assert_eq!(attempts.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn model_worker_accounts_for_failed_and_following_jobs() {
        let jobs: Vec<_> = (0..3).map(|_| Arc::new(Pending::default())).collect();
        let waiting = Arc::new(AtomicUsize::new(jobs.len()));
        let worker_jobs = jobs.clone();
        let worker_waiting = waiting.clone();
        let (tx, rx) = mpsc::channel();
        let thread = std::thread::spawn(move || {
            for (i, p) in worker_jobs.into_iter().enumerate() {
                p.make(|| match i {
                    0 => panic!("synthetic build"),
                    1 => Some(71),
                    _ => None,
                });
                let old = worker_waiting.fetch_sub(1, Ordering::Relaxed);
                tx.send((i, *p.made.get().unwrap(), old)).unwrap();
            }
        });
        for expected in [(0, None, 3), (1, Some(71), 2), (2, None, 1)] {
            assert_eq!(rx.recv_timeout(LIMIT).unwrap(), expected);
        }
        thread.join().unwrap();
        assert_eq!(waiting.load(Ordering::Relaxed), 0);
        assert_eq!(jobs[0].made.get(), Some(&None));
        assert_eq!(jobs[1].made.get(), Some(&Some(71)));
        assert_eq!(jobs[2].made.get(), Some(&None));
    }
}
