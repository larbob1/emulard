// Test-only gates for actual Pool::submit / Pool::work, never a production policy.
#[cfg(test)]
mod hle_pool_gated_native_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};
    use std::time::Instant;

    const LIMIT: Duration = Duration::from_secs(5);
    type Gate = mpsc::Sender<()>;
    static STARTS: OnceLock<mpsc::Sender<Gate>> = OnceLock::new();
    static EVENTS: OnceLock<mpsc::Sender<(usize, bool)>> = OnceLock::new();
    static RELEASE: OnceLock<Mutex<Option<mpsc::Receiver<()>>>> = OnceLock::new();

    // Called before the actual worker acquires the state mutex. Only a
    // fresh-process ignored test installs STARTS. Timeout bounds test gates.
    pub(super) fn before_work() {
        if let Some(starts) = STARTS.get() {
            let (gate, wait) = mpsc::channel();
            if starts.send(gate).is_ok() {
                let _ = wait.recv_timeout(LIMIT * 4);
            }
        }
    }

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        if let Some(events) = EVENTS.get() {
            let _ = events.send((context as usize, !canceled));
        }
    }

    extern "system" fn blocked(_: *mut c_void, canceled: bool) {
        let Some(events) = EVENTS.get() else { return };
        let _ = events.send((3, !canceled));
        let rx = RELEASE.get().and_then(|m| m.lock().ok())
            .and_then(|mut slot| slot.take());
        let ok = !canceled && rx.is_some_and(|rx| rx.recv_timeout(LIMIT) == Ok(()));
        let _ = events.send((5, ok));
    }

    fn wait_idle(pool: &Pool, expected: usize) {
        let deadline = Instant::now() + LIMIT;
        loop {
            {
                let state = lock(&pool.state);
                if state.0.is_empty() && state.1 == expected { return; }
            }
            assert!(Instant::now() < deadline, "worker did not become idle");
            // Test observation only; the actual workers use Condvar.
            std::thread::sleep(Duration::from_millis(1));
        }
    }

    #[test]
    #[ignore = "fresh-process actual baseline pool start-gate observation"]
    fn pending_start_and_idle_notification() {
        let (start_tx, start_rx) = mpsc::channel();
        let (event_tx, event_rx) = mpsc::channel();
        let (release_tx, release_rx) = mpsc::channel();
        assert!(STARTS.set(start_tx).is_ok());
        assert!(EVENTS.set(event_tx).is_ok());
        assert!(RELEASE.set(Mutex::new(Some(release_rx))).is_ok());

        // Pool::submit needs a static receiver; workers deliberately persist.
        // Use a distinct pool and let the isolated test process own its lifetime.
        let pool: &'static Pool = Box::leak(Box::new(Pool {
            state: Mutex::new((VecDeque::new(), 0)),
            ready: Condvar::new(),
        }));
        pool.submit(Task::new(1usize as *mut c_void, report));
        let first = start_rx.recv_timeout(LIMIT).expect("first start");
        pool.submit(Task::new(2usize as *mut c_void, report));
        let pending = start_rx.recv_timeout(LIMIT).expect("second start");
        first.send(()).unwrap();
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (1, true));
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (2, true));
        wait_idle(pool, 1);

        // This submission wakes the existing idle worker; it then blocks.
        pool.submit(Task::new(std::ptr::null_mut(), blocked));
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (3, true));
        // Baseline sees zero idle workers, despite the pending second start.
        pool.submit(Task::new(4usize as *mut c_void, report));
        let redundant = start_rx.recv_timeout(LIMIT).expect("baseline third start");
        // Release only the previously pending worker. Third remains gated.
        pending.send(()).unwrap();
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (4, true));
        release_tx.send(()).unwrap();
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (5, true));
        redundant.send(()).unwrap();
        wait_idle(pool, 3);
        assert!(event_rx.try_recv().is_err(), "duplicate callback event");
        assert!(start_rx.try_recv().is_err(), "unexpected extra spawn");
    }
}
