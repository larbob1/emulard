// Test-only injection of the baseline spawn panic boundary.
// Not an OS resource-exhaustion test or an alternative recovery policy.
#[cfg(test)]
mod hle_pool_spawn_failure_review {
    use super::*;
    use std::panic::{catch_unwind, AssertUnwindSafe};
    use std::sync::{OnceLock, mpsc};
    use std::time::Instant;

    const LIMIT: Duration = Duration::from_secs(5);
    static FAIL_NEXT: AtomicBool = AtomicBool::new(false);
    static EVENTS: OnceLock<mpsc::Sender<(usize, bool)>> = OnceLock::new();

    pub(super) fn before_spawn() {
        if FAIL_NEXT.swap(false, Ordering::SeqCst) {
            // Like std::thread::spawn's panic on creation failure, unwind
            // while Pool::submit still holds the state mutex. No OS failure
            // is induced and no callback or extern boundary is unwound.
            panic!("synthetic spawn failure");
        }
    }

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        if let Some(events) = EVENTS.get() {
            let _ = events.send((context as usize, !canceled));
        }
    }

    #[test]
    #[ignore = "fresh-process baseline spawn panic observation"]
    fn spawn_panic_preserves_queued_work() {
        let (event_tx, event_rx) = mpsc::channel();
        assert!(EVENTS.set(event_tx).is_ok());

        let pool: &'static Pool = Box::leak(Box::new(Pool {
            state: Mutex::new((VecDeque::new(), 0)),
            ready: Condvar::new(),
        }));
        FAIL_NEXT.store(true, Ordering::SeqCst);
        let result = catch_unwind(AssertUnwindSafe(|| {
            pool.submit(Task::new(1usize as *mut c_void, report));
        }));
        assert!(result.is_err(), "expected injected spawn panic");
        assert!(!FAIL_NEXT.load(Ordering::SeqCst));
        assert!(pool.state.is_poisoned());
        {
            // Use the runtime's existing poison-recovering lock helper.
            let state = lock(&pool.state);
            assert_eq!(state.0.len(), 1);
            assert_eq!(state.1, 0);
        }
        assert!(event_rx.try_recv().is_err());

        // Subsequent submit, not an automatic retry, permits both queued
        // callbacks to complete through the unchanged baseline worker loop.
        pool.submit(Task::new(2usize as *mut c_void, report));
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (1, true));
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (2, true));

        let deadline = Instant::now() + LIMIT;
        loop {
            {
                let state = lock(&pool.state);
                if state.0.is_empty() && state.1 == 1 { break; }
            }
            assert!(Instant::now() < deadline, "worker did not become idle");
            std::thread::sleep(Duration::from_millis(1));
        }
        assert!(event_rx.try_recv().is_err(), "duplicate callback event");
        // Do not clear poison, change error handling, or introduce shutdown.
        assert!(pool.state.is_poisoned());
    }
}
