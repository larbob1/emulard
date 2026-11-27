// SPDX-License-Identifier: GPL-3.0-or-later
// Actual baseline shared-manual-port characterization, not a policy change.
#[cfg(test)]
mod hle_manual_termination_native_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};

    static EVENTS: OnceLock<mpsc::Sender<(usize, bool)>> = OnceLock::new();

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((context as usize, canceled));
        }
    }

    struct Handle(*const Queue);
    impl Drop for Handle {
        fn drop(&mut self) { XTaskQueueCloseHandle(self.0); }
    }

    fn composite(port: *const c_void) -> Handle {
        let mut handle = Handle(std::ptr::null());
        assert_eq!(XTaskQueueCreateComposite(port, port, &mut handle.0), S_OK);
        assert!(!handle.0.is_null());
        handle
    }

    fn submit(handle: &Handle, slot: u32, id: usize) -> HRESULT {
        XTaskQueueSubmitDelayedCallback(handle.0, slot, 0, id as *mut c_void,
                                        Some(report))
    }

    fn receipt(rx: &mpsc::Receiver<(usize, bool)>, id: usize) {
        // Manual dispatch calls the callback synchronously.
        assert_eq!(rx.try_recv(), Ok((id, false)));
        assert!(rx.try_recv().is_err());
    }

    #[test]
    #[ignore = "fresh process; actual shared manual dispatch baseline"]
    fn terminated_manual_queue_can_claim_survivor_work() {
        let (tx, rx) = mpsc::channel();
        assert!(EVENTS.set(tx).is_ok());
        let mut original = Handle(std::ptr::null());
        assert_eq!(XTaskQueueCreate(0, 0, &mut original.0), S_OK);
        assert!(!original.0.is_null());
        let mut port = std::ptr::null();
        assert_eq!(XTaskQueueGetPort(original.0, WORK, &mut port), S_OK);
        assert!(!port.is_null());
        let weak = {
            let owner = queue(original.0).expect("live original");
            Arc::downgrade(&owner.ports[WORK as usize])
        };
        let ending = composite(port);
        let survivor = composite(port);
        for handle in [&ending, &survivor] {
            let owner = queue(handle.0).expect("live composite");
            assert!(Arc::ptr_eq(&owner.ports[0], &owner.ports[1]));
            assert_eq!(Arc::as_ptr(&owner.ports[0]).cast::<c_void>(), port);
            assert_eq!(owner.ports[0].mode, Mode::Manual);
        }
        drop(original);
        assert_eq!(weak.strong_count(), 4);

        // Both queues start empty; termination sets only ending's flag.
        assert_eq!(XTaskQueueTerminate(ending.0, false, std::ptr::null_mut(),
                                      None), S_OK);
        assert!(queue(ending.0).unwrap().terminated.load(Ordering::Acquire));
        assert!(!queue(survivor.0).unwrap().terminated.load(Ordering::Acquire));
        assert!(!XTaskQueueDispatch(ending.0, WORK, 0));
        assert!(!XTaskQueueDispatch(ending.0, COMPLETION, 0));
        assert_eq!(submit(&ending, WORK, 99), E_ABORT);
        assert_eq!(submit(&ending, COMPLETION, 100), E_ABORT);
        assert!(rx.try_recv().is_err());

        // The task is available on the shared port. The terminated flag
        // ends waiting, but the pinned implementation still pops a task.
        assert_eq!(submit(&survivor, COMPLETION, 1), S_OK);
        assert!(rx.try_recv().is_err());
        assert!(XTaskQueueDispatch(ending.0, WORK, 0));
        receipt(&rx, 1);
        assert!(!XTaskQueueDispatch(survivor.0, COMPLETION, 0));

        // FIFO is shared even across the aliased work/completion slots.
        assert_eq!(submit(&survivor, WORK, 2), S_OK);
        assert_eq!(submit(&survivor, COMPLETION, 3), S_OK);
        assert!(rx.try_recv().is_err());
        assert!(XTaskQueueDispatch(ending.0, COMPLETION, 0));
        receipt(&rx, 2);
        assert!(XTaskQueueDispatch(survivor.0, WORK, 0));
        receipt(&rx, 3);
        assert!(!XTaskQueueDispatch(ending.0, WORK, 0));

        // Closing ending releases only its two slots; survivor still works.
        drop(ending);
        assert_eq!(weak.strong_count(), 2);
        assert_eq!(submit(&survivor, WORK, 4), S_OK);
        assert!(XTaskQueueDispatch(survivor.0, COMPLETION, 0));
        receipt(&rx, 4);
        assert!(!XTaskQueueDispatch(survivor.0, WORK, 0));
        drop(survivor);
        assert_eq!(weak.strong_count(), 0);
        assert!(rx.try_recv().is_err());
        eprintln!("AI6 manual_termination baseline callbacks=4 terminated_claims=2 rejected=2 port_released=1");
    }
}
