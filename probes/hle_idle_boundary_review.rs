// Controlled interleavings of the test-only idle retirement clone.
#[cfg(test)]
mod hle_idle_boundary_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};
    use std::time::Instant;

    // @POOL_CLONE@

    const LIMIT: Duration = Duration::from_secs(5);
    static EPOCH: AtomicUsize = AtomicUsize::new(0);
    static LAST: AtomicUsize = AtomicUsize::new(usize::MAX);
    static OBSERVED: OnceLock<mpsc::Sender<usize>> = OnceLock::new();
    static EVENTS: OnceLock<mpsc::Sender<usize>> = OnceLock::new();
    static GATE: OnceLock<mpsc::Sender<(usize, usize, mpsc::Sender<()>)>> = OnceLock::new();
    static RELEASED: AtomicBool = AtomicBool::new(false);
    static GATED: AtomicBool = AtomicBool::new(false);

    fn observe_wait(empty: bool) -> bool {
        if empty {
            let epoch = EPOCH.load(Ordering::SeqCst);
            if LAST.swap(epoch, Ordering::SeqCst) != epoch {
                if let Some(tx) = OBSERVED.get() { let _ = tx.send(epoch); }
            }
        }
        empty
    }

    // Called under the clone's state lock, before availability is removed.
    fn after_wait(queued: usize, idle: usize) {
        if let Some(tx) = GATE.get() {
            if !GATED.swap(true, Ordering::SeqCst) {
                let (release, wait) = mpsc::channel();
                if tx.send((queued, idle, release)).is_ok() {
                    RELEASED.store(wait.recv_timeout(LIMIT * 3).is_ok(), Ordering::SeqCst);
                }
            }
        }
    }

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send(if canceled { usize::MAX } else { context as usize });
        }
    }

    fn pool(timeout: Duration) -> &'static ReviewPool {
        Box::leak(Box::new(ReviewPool {
            state: Mutex::new((VecDeque::new(), 0)),
            ready: Condvar::new(),
            timeout: Some(timeout),
            retired: AtomicUsize::new(0),
        }))
    }

    fn submit(pool: &'static ReviewPool, id: usize) {
        pool.submit(Task::new(id as *mut c_void, report));
    }

    fn until_retired(pool: &ReviewPool, expected: usize) {
        let deadline = Instant::now() + LIMIT;
        loop {
            {
                let state = lock(&pool.state);
                if state.0.is_empty() && state.1 == 0
                    && pool.retired.load(Ordering::SeqCst) == expected { return; }
            }
            assert!(Instant::now() < deadline, "retirement watchdog");
            std::thread::sleep(Duration::from_millis(1));
        }
    }

    #[test]
    #[ignore = "fresh-process controlled empty notification and submit-first"]
    fn empty_wake_then_submission_reuses_idle_worker() {
        let (tx, rx) = mpsc::channel();
        let (obs_tx, obs_rx) = mpsc::channel();
        let (gate_tx, gate_rx) = mpsc::channel();
        assert!(EVENTS.set(tx).is_ok());
        assert!(OBSERVED.set(obs_tx).is_ok());
        assert!(GATE.set(gate_tx).is_ok());
        // Long illustrative timeout avoids depending on exact timer accuracy.
        let pool = pool(Duration::from_secs(60));
        submit(pool, 1);
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 1);
        assert_eq!(obs_rx.recv_timeout(LIMIT).unwrap(), 0);
        {
            let state = lock(&pool.state);
            assert_eq!((state.0.len(), state.1), (0, 1));
            EPOCH.store(1, Ordering::SeqCst);
            pool.ready.notify_all();
        }
        // Predicate was observed empty after the notification epoch changed.
        assert_eq!(obs_rx.recv_timeout(LIMIT).unwrap(), 1);
        {
            let state = lock(&pool.state);
            assert_eq!((state.0.len(), state.1), (0, 1));
            assert_eq!(pool.retired.load(Ordering::SeqCst), 0);
        }
        submit(pool, 2);
        let (queued, idle, release) = gate_rx.recv_timeout(LIMIT).unwrap();
        assert_eq!((queued, idle), (1, 1));
        assert!(rx.try_recv().is_err());
        release.send(()).unwrap();
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 2);
        assert_eq!(pool.retired.load(Ordering::SeqCst), 0);
        assert!(RELEASED.load(Ordering::SeqCst), "gate release not received");
        assert!(rx.try_recv().is_err());
        // Workers persist only until this isolated process exits.
    }

    #[test]
    #[ignore = "fresh-process controlled timeout-first interleaving"]
    fn expiry_holds_lock_then_submission_starts_replacement() {
        let (tx, rx) = mpsc::channel();
        let (gate_tx, gate_rx) = mpsc::channel();
        assert!(EVENTS.set(tx).is_ok());
        assert!(GATE.set(gate_tx).is_ok());
        let pool = pool(Duration::from_millis(50));
        submit(pool, 1);
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 1);
        let (queued, idle, release) = gate_rx.recv_timeout(LIMIT).unwrap();
        assert_eq!((queued, idle), (0, 1));
        let (contended_tx, contended_rx) = mpsc::channel();
        let (done_tx, done_rx) = mpsc::channel();
        let submitter = std::thread::spawn(move || {
            // The retirement gate is still closed. Observe the actual mutex
            // rather than merely announce that submission is about to start.
            assert!(matches!(pool.state.try_lock(), Err(std::sync::TryLockError::WouldBlock)));
            contended_tx.send(()).unwrap();
            submit(pool, 2);
            done_tx.send(()).unwrap();
        });
        contended_rx.recv_timeout(LIMIT).unwrap();
        // The submitter observed actual contention while the gate was closed.
        // This does not assert when its subsequent blocking lock call starts.
        assert!(done_rx.try_recv().is_err());
        assert!(rx.try_recv().is_err());
        release.send(()).unwrap();
        done_rx.recv_timeout(LIMIT).unwrap();
        submitter.join().unwrap();
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 2);
        until_retired(pool, 2);
        assert!(RELEASED.load(Ordering::SeqCst), "gate release not received");
        assert!(rx.try_recv().is_err());
    }
}
