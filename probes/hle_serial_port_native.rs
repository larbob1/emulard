// Actual baseline serialized port lifetime, no polling-policy change.
#[cfg(test)]
mod hle_serial_port_native_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};
    use std::time::Instant;

    const LIMIT: Duration = Duration::from_secs(5);
    static EVENTS: OnceLock<mpsc::Sender<(usize, bool)>> = OnceLock::new();
    static RELEASE: OnceLock<Mutex<Option<mpsc::Receiver<()>>>> = OnceLock::new();
    static RELEASED: AtomicBool = AtomicBool::new(false);

    extern "system" fn blocked(_: *mut c_void, canceled: bool) {
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((1, !canceled));
        }
        let rx = RELEASE.get().and_then(|m| m.lock().ok())
            .and_then(|mut slot| slot.take());
        let ok = rx.is_some_and(|rx| rx.recv_timeout(LIMIT * 3).is_ok());
        RELEASED.store(ok, Ordering::SeqCst);
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((2, ok && !canceled));
        }
    }

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((context as usize, !canceled));
        }
    }

    #[test]
    #[ignore = "fresh-process serialized port ownership baseline"]
    fn shared_serial_port_drains_after_last_queue_close() {
        let (tx, rx) = mpsc::channel();
        let (release_tx, release_rx) = mpsc::channel();
        assert!(EVENTS.set(tx).is_ok());
        assert!(RELEASE.set(Mutex::new(Some(release_rx))).is_ok());

        let q = Queue::new([Port::new(Mode::Serialized), Port::new(Mode::Manual)]);
        let weak_port = Arc::downgrade(&q.ports[WORK as usize]);
        let weak_q = Arc::downgrade(&q);
        let original = Arc::into_raw(q);
        let (mut work, mut completion) = (std::ptr::null(), std::ptr::null());
        assert_eq!(XTaskQueueGetPort(original, WORK, &mut work), S_OK);
        assert_eq!(XTaskQueueGetPort(original, COMPLETION, &mut completion), S_OK);
        let mut composite = std::ptr::null();
        assert_eq!(XTaskQueueCreateComposite(work, completion, &mut composite), S_OK);
        XTaskQueueCloseHandle(original);
        assert!(weak_q.upgrade().is_none());
        assert!(weak_port.upgrade().is_some());

        // The composite must still use the same serialized worker after
        // its original queue is destroyed. No caller retains a port Arc.
        assert_eq!(XTaskQueueSubmitDelayedCallback(composite, WORK, 0,
            std::ptr::null_mut(), Some(blocked)), S_OK);
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (1, true));
        for id in [3usize, 4] {
            assert_eq!(XTaskQueueSubmitDelayedCallback(composite, WORK, 0,
                id as *mut c_void, Some(report)), S_OK);
        }
        assert!(rx.try_recv().is_err(), "serialized worker ran queued task while blocked");
        XTaskQueueCloseHandle(composite);
        // No more handle calls. The worker itself holds the remaining Arc.
        assert!(weak_port.upgrade().is_some());
        release_tx.send(()).unwrap();
        for id in [2usize, 3, 4] {
            assert_eq!(rx.recv_timeout(LIMIT).unwrap(), (id, true));
        }
        assert!(RELEASED.load(Ordering::SeqCst));
        let deadline = Instant::now() + LIMIT;
        // weak::strong_count observes without prolonging the port lifetime.
        while weak_port.strong_count() != 0 {
            assert!(Instant::now() < deadline, "serialized port lifetime watchdog");
            std::thread::sleep(Duration::from_millis(10));
        }
        assert!(weak_port.upgrade().is_none());
        assert!(rx.try_recv().is_err());
        // This proves port ownership release, not exact OS thread exit time.
    }
}
