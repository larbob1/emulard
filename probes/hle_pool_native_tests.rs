// Test-only module for the pinned victory-hle xasync.rs. Never registered by this branch.
#[cfg(test)]
mod hle_pool_native_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};
    use std::sync::atomic::AtomicUsize;

    const LIMIT: Duration = Duration::from_secs(5);

    struct Context {
        dependent_tx: mpsc::Sender<bool>,
        dependent_rx: Mutex<Option<mpsc::Receiver<bool>>>,
        done_tx: mpsc::Sender<bool>,
        first_count: AtomicUsize,
        second_count: AtomicUsize,
    }

    static CONTEXT: OnceLock<Context> = OnceLock::new();

    extern "system" fn dependent(_: *mut c_void, canceled: bool) {
        if let Some(c) = CONTEXT.get() {
            c.second_count.fetch_add(1, Ordering::SeqCst);
            let _ = c.dependent_tx.send(!canceled);
        }
    }

    extern "system" fn parent(queue: *mut c_void, canceled: bool) {
        let Some(c) = CONTEXT.get() else { return };
        c.first_count.fetch_add(1, Ordering::SeqCst);
        // No assertions or unwraps across the extern callback boundary.
        let rx = c.dependent_rx.lock().ok().and_then(|mut slot| slot.take());
        let ok = !canceled
            && XTaskQueueSubmitDelayedCallback(
                queue.cast::<Queue>(), WORK, 0, std::ptr::null_mut(), Some(dependent)
            ) == S_OK
            && rx.is_some_and(|rx| rx.recv_timeout(LIMIT) == Ok(true));
        let _ = c.done_tx.send(ok);
    }

    // Run exactly this ignored test in a fresh process. The runtime's global
    // worker pool deliberately persists; no test-only shutdown is introduced.
    #[test]
    #[ignore = "fresh-process native HLE review; register explicitly"]
    fn reentrant_pool_callback_progress() {
        let (dependent_tx, dependent_rx) = mpsc::channel();
        let (done_tx, done_rx) = mpsc::channel();
        assert!(CONTEXT.set(Context {
            dependent_tx,
            dependent_rx: Mutex::new(Some(dependent_rx)),
            done_tx,
            first_count: AtomicUsize::new(0),
            second_count: AtomicUsize::new(0),
        }).is_ok(), "fixture must run in a fresh process");
        let mut queue = std::ptr::null();
        assert_eq!(XTaskQueueCreate(1, 0, &mut queue), S_OK);
        assert!(!queue.is_null());
        assert_eq!(XTaskQueueSubmitDelayedCallback(
            queue, WORK, 0, queue.cast_mut().cast(), Some(parent)
        ), S_OK);
        // If the outer watchdog times out, leave the handle alive until the
        // isolated test process exits: a callback may still use it.
        let ok = done_rx.recv_timeout(LIMIT + LIMIT)
            .expect("parent callback did not report before watchdog");
        XTaskQueueCloseHandle(queue);
        assert!(ok, "reentrant dependent callback did not complete");
        let c = CONTEXT.get().unwrap();
        assert_eq!(c.first_count.load(Ordering::SeqCst), 1);
        assert_eq!(c.second_count.load(Ordering::SeqCst), 1);
    }
}
