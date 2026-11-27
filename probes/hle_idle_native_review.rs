// Test-only clone of the pinned pool. No production timeout or flag.
#[cfg(test)]
mod hle_idle_native_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};
    use std::time::Instant;

    // @POOL_CLONE@

    const LIMIT: Duration = Duration::from_secs(5);
    static EVENTS: OnceLock<mpsc::Sender<(usize, bool)>> = OnceLock::new();
    static DEPENDENCY: OnceLock<Mutex<Option<mpsc::Receiver<bool>>>> = OnceLock::new();
    static SIGNAL: OnceLock<mpsc::Sender<bool>> = OnceLock::new();

    extern "system" fn dependent(_: *mut c_void, canceled: bool) {
        if let Some(tx) = SIGNAL.get() {
            let _ = tx.send(!canceled);
        }
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((2, !canceled));
        }
    }

    extern "system" fn parent(context: *mut c_void, canceled: bool) {
        // SAFETY: the fixture passes a leaked, static ReviewPool pointer.
        let pool = unsafe { &*context.cast::<ReviewPool>() };
        let rx = DEPENDENCY.get().and_then(|m| m.lock().ok())
            .and_then(|mut slot| slot.take());
        pool.submit(Task::new(std::ptr::null_mut(), dependent));
        let ok = !canceled && rx.is_some_and(|rx| rx.recv_timeout(LIMIT) == Ok(true));
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((1, ok));
        }
    }

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((context as usize, !canceled));
        }
    }

    fn await_state(pool: &ReviewPool, idle: usize, retired: usize) {
        let deadline = Instant::now() + LIMIT;
        loop {
            {
                let s = lock(&pool.state);
                if s.0.is_empty() && s.1 == idle
                    && pool.retired.load(Ordering::SeqCst) == retired { return; }
            }
            assert!(Instant::now() < deadline, "pool state watchdog");
            std::thread::sleep(Duration::from_millis(1));
        }
    }

    fn exercise(timeout: Option<Duration>) {
        let (tx, rx) = mpsc::channel();
        let (signal_tx, signal_rx) = mpsc::channel();
        assert!(EVENTS.set(tx).is_ok());
        assert!(SIGNAL.set(signal_tx).is_ok());
        assert!(DEPENDENCY.set(Mutex::new(Some(signal_rx))).is_ok());
        let pool: &'static ReviewPool = Box::leak(Box::new(ReviewPool {
            state: Mutex::new((VecDeque::new(), 0)),
            ready: Condvar::new(),
            timeout,
            retired: AtomicUsize::new(0),
        }));
        pool.submit(Task::new(std::ptr::from_ref(pool).cast_mut().cast(), parent));
        let mut events = [rx.recv_timeout(LIMIT).unwrap(), rx.recv_timeout(LIMIT).unwrap()];
        events.sort_unstable();
        assert_eq!(events, [(1, true), (2, true)]);
        if timeout.is_some() {
            await_state(pool, 0, 2);
        } else {
            await_state(pool, 2, 0);
        }
        // Empty notifications cannot create work. The candidate must
        // still retire after the next task, while baseline retains workers.
        pool.ready.notify_all();
        pool.submit(Task::new(3usize as *mut c_void, report));
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (3, true));
        if timeout.is_some() {
            await_state(pool, 0, 3);
        } else {
            await_state(pool, 2, 0);
        }
        assert!(rx.try_recv().is_err());
        // retired counts the locked removal from availability, not OS exit.
    }

    #[test]
    #[ignore = "fresh-process exact baseline clone"]
    fn idle_native_baseline() { exercise(None); }

    #[test]
    #[ignore = "fresh-process test-only retirement clone"]
    fn idle_native_candidate() { exercise(Some(Duration::from_millis(50))); }
}
