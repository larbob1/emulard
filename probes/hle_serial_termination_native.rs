// SPDX-License-Identifier: GPL-3.0-or-later
// Append-only baseline characterization of the pinned HLE implementation.
// No proposed cancellation, scheduling, or port-lifetime policy changes.
#[cfg(test)]
mod hle_serial_termination_native_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};
    use std::time::Instant;

    type Event = (usize, bool, HRESULT);
    const LIMIT: Duration = Duration::from_secs(5);
    static EVENTS: OnceLock<mpsc::Sender<Event>> = OnceLock::new();
    static GATE: OnceLock<Mutex<Option<mpsc::Receiver<()>>>> = OnceLock::new();
    static SURVIVOR: AtomicUsize = AtomicUsize::new(0);

    fn emit(id: usize, canceled: bool, result: HRESULT) {
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((id, canceled, result));
        }
    }

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        emit(context as usize, canceled, S_OK);
    }

    extern "system" fn blocked(_: *mut c_void, canceled: bool) {
        emit(1, canceled, S_OK);
        let receiver = GATE.get().and_then(|m| m.lock().ok())
            .and_then(|mut slot| slot.take());
        let released = receiver.is_some_and(|r| r.recv_timeout(LIMIT * 4).is_ok());
        emit(5, canceled, if released { S_OK } else { E_ABORT });
    }

    extern "system" fn reenter(_: *mut c_void, canceled: bool) {
        // The harness retains the survivor handle until termination returns.
        // Report errors to the harness rather than panic across the ABI.
        let handle = SURVIVOR.load(Ordering::Acquire) as *const Queue;
        let result = if handle.is_null() {
            E_INVALIDARG
        } else {
            XTaskQueueSubmitDelayedCallback(handle, WORK, 0,
                3usize as *mut c_void, Some(report))
        };
        emit(2, canceled, result);
    }

    extern "system" fn terminated(_: *mut c_void) {
        emit(4, false, S_OK);
    }

    struct Handle(*const Queue);
    impl Drop for Handle {
        fn drop(&mut self) {
            XTaskQueueCloseHandle(self.0);
        }
    }

    fn composite(port: *const c_void) -> Handle {
        let mut handle = Handle(std::ptr::null());
        assert_eq!(XTaskQueueCreateComposite(port, port, &mut handle.0), S_OK);
        assert!(!handle.0.is_null());
        handle
    }

    fn expect(rx: &mpsc::Receiver<Event>, id: usize, canceled: bool) {
        assert_eq!(rx.recv_timeout(LIMIT).expect("callback receipt watchdog"),
                   (id, canceled, S_OK));
    }

    #[test]
    #[ignore = "fresh process; actual shared serialized cancellation baseline"]
    fn actual_aliased_serial_termination_reentry() {
        let (tx, rx) = mpsc::channel();
        let (release, wait) = mpsc::channel();
        assert!(EVENTS.set(tx).is_ok());
        assert!(GATE.set(Mutex::new(Some(wait))).is_ok());

        // Use exported creation and borrowed-port APIs, not a copied model.
        let mut original = Handle(std::ptr::null());
        assert_eq!(XTaskQueueCreate(2, 0, &mut original.0), S_OK);
        let mut port = std::ptr::null();
        assert_eq!(XTaskQueueGetPort(original.0, WORK, &mut port), S_OK);
        assert!(!port.is_null());
        let weak = {
            let owner = queue(original.0).expect("live original");
            Arc::downgrade(&owner.ports[WORK as usize])
        };
        let ending = composite(port);
        let surviving = composite(port);
        // Both composites alias exactly the same serialized port twice.
        for handle in [&ending, &surviving] {
            let owner = queue(handle.0).expect("live composite");
            assert!(Arc::ptr_eq(&owner.ports[0], &owner.ports[1]));
            assert_eq!(Arc::as_ptr(&owner.ports[0]).cast::<c_void>(), port);
        }
        drop(original);
        // No subsequent use of the original borrowed port or queue.
        assert_eq!(weak.strong_count(), 5); // two slots per composite + worker
        SURVIVOR.store(surviving.0 as usize, Ordering::Release);

        assert_eq!(XTaskQueueSubmitDelayedCallback(ending.0, WORK, 0,
            std::ptr::null_mut(), Some(blocked)), S_OK);
        expect(&rx, 1, false);
        assert_eq!(XTaskQueueSubmitDelayedCallback(ending.0, WORK, 0,
            std::ptr::null_mut(), Some(reenter)), S_OK);

        // First slot drains reenter; its accepted task is queued on the
        // open survivor and drained by the second aliased slot. The active
        // worker remains gated so it cannot claim either pending callback.
        assert_eq!(XTaskQueueTerminate(ending.0, false, std::ptr::null_mut(),
            Some(terminated)), S_OK);
        expect(&rx, 2, true);
        expect(&rx, 3, true);
        expect(&rx, 4, false);
        SURVIVOR.store(0, Ordering::Release);

        assert_eq!(XTaskQueueSubmitDelayedCallback(ending.0, WORK, 0,
            99usize as *mut c_void, Some(report)), E_ABORT);
        assert_eq!(XTaskQueueSubmitDelayedCallback(surviving.0, COMPLETION, 0,
            6usize as *mut c_void, Some(report)), S_OK);
        assert_eq!(XTaskQueueSubmitDelayedCallback(surviving.0, WORK, 0,
            7usize as *mut c_void, Some(report)), S_OK);
        drop(ending);
        assert_eq!(weak.strong_count(), 3);
        // Final close must retain the already accepted work on the port.
        drop(surviving);
        assert_eq!(weak.strong_count(), 1);
        assert!(rx.try_recv().is_err());
        release.send(()).expect("active worker still waiting");
        expect(&rx, 5, false);
        expect(&rx, 6, false);
        expect(&rx, 7, false);

        let deadline = Instant::now() + LIMIT;
        while weak.strong_count() != 0 {
            assert!(Instant::now() < deadline, "serialized port retirement watchdog");
            std::thread::sleep(Duration::from_millis(10));
        }
        assert!(rx.try_recv().is_err(), "unexpected duplicate/rejected callback");
        // This observes Arc ownership release, not OS thread termination.
        eprintln!("AI6 serial_termination baseline events=7 task_callbacks=5 termination_callbacks=1 canceled=2 rejected=1 port_released=1");
    }
}
