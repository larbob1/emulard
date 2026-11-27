// Baseline characterization, not approval of late delivery semantics.
#[cfg(test)]
mod hle_delayed_native_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};
    use std::time::Instant;

    const LIMIT: Duration = Duration::from_secs(5);
    static GATES: OnceLock<mpsc::Sender<mpsc::Sender<()>>> = OnceLock::new();
    static EVENTS: OnceLock<mpsc::Sender<(usize, bool)>> = OnceLock::new();
    static MONITORS: OnceLock<mpsc::Sender<u32>> = OnceLock::new();

    pub(super) fn before_deliver() {
        if let Some(gates) = GATES.get() {
            let (release, wait) = mpsc::channel();
            if gates.send(release).is_ok() {
                let _ = wait.recv_timeout(LIMIT * 4);
            }
        }
    }

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        if let Some(events) = EVENTS.get() {
            let _ = events.send((context as usize, canceled));
        }
    }

    extern "system" fn monitor(_: *mut c_void, _: *const Queue, port: u32) {
        if let Some(monitors) = MONITORS.get() {
            let _ = monitors.send(port);
        }
    }

    #[test]
    #[ignore = "fresh-process baseline delayed delivery observation"]
    fn delayed_queue_lifetime_and_termination() {
        let (gate_tx, gate_rx) = mpsc::channel();
        let (event_tx, event_rx) = mpsc::channel();
        let (monitor_tx, monitor_rx) = mpsc::channel();
        assert!(GATES.set(gate_tx).is_ok());
        assert!(EVENTS.set(event_tx).is_ok());
        assert!(MONITORS.set(monitor_tx).is_ok());

        // Delayed worker owns a queue reference after the caller closes it.
        let q = Queue::new([Port::new(Mode::Immediate), Port::new(Mode::Manual)]);
        let weak = Arc::downgrade(&q);
        let mut token = 0;
        assert_eq!(XTaskQueueRegisterMonitor(
            Arc::as_ptr(&q), std::ptr::null_mut(), Some(monitor), &mut token
        ), S_OK);
        assert_eq!(q.submit(WORK, 1, Task::new(1usize as *mut c_void, report)), S_OK);
        let release = gate_rx.recv_timeout(LIMIT).expect("delayed worker reached gate");
        drop(q);
        assert!(weak.upgrade().is_some(), "delayed task must retain queue");
        assert!(event_rx.try_recv().is_err());
        assert!(monitor_rx.try_recv().is_err());
        release.send(()).unwrap();
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (1, false));
        assert_eq!(monitor_rx.recv_timeout(LIMIT).unwrap(), WORK);
        let deadline = Instant::now() + LIMIT;
        while weak.upgrade().is_some() {
            assert!(Instant::now() < deadline, "queue not released");
            std::thread::sleep(Duration::from_millis(1));
        }

        // Existing behavior: termination drains currently queued tasks;
        // a delayed task held outside the port still delivers afterward.
        // Record this behavior for future compatibility review, not as a
        // statement that it conforms to the external API specification.
        let q = Queue::new([Port::new(Mode::Manual), Port::new(Mode::Manual)]);
        let handle = Arc::as_ptr(&q);
        assert_eq!(XTaskQueueRegisterMonitor(
            handle, std::ptr::null_mut(), Some(monitor), &mut token
        ), S_OK);
        assert_eq!(q.submit(WORK, 1, Task::new(2usize as *mut c_void, report)), S_OK);
        let release = gate_rx.recv_timeout(LIMIT).unwrap();
        assert_eq!(XTaskQueueTerminate(handle, false, std::ptr::null_mut(), None), S_OK);
        assert_eq!(q.submit(WORK, 0, Task::new(3usize as *mut c_void, report)), E_ABORT);
        assert!(!XTaskQueueDispatch(handle, WORK, 0));
        assert!(event_rx.try_recv().is_err());
        assert!(monitor_rx.try_recv().is_err());
        release.send(()).unwrap();
        assert_eq!(monitor_rx.recv_timeout(LIMIT).unwrap(), WORK);
        assert!(event_rx.try_recv().is_err(), "manual callback requires dispatch");
        assert!(XTaskQueueDispatch(handle, WORK, 0));
        assert_eq!(event_rx.recv_timeout(LIMIT).unwrap(), (2, false));
        assert!(!XTaskQueueDispatch(handle, WORK, 0));
        assert!(event_rx.try_recv().is_err());
        assert!(monitor_rx.try_recv().is_err());
    }
}
