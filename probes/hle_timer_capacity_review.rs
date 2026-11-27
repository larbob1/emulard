// Review-only timer/dispatcher capacity experiments. No runtime policy.
use std::collections::VecDeque;
use std::sync::{Arc, mpsc};
use std::thread;
use std::time::Duration;

const LIMIT: Duration = Duration::from_secs(5);

#[test]
fn full_blocking_channel_stalls_later_handoff() {
    let (tx, rx) = mpsc::sync_channel(1);
    tx.send(1).unwrap();
    let (entered_tx, entered_rx) = mpsc::channel();
    let (after_tx, after_rx) = mpsc::channel();
    let timer = thread::spawn(move || {
        entered_tx.send(()).unwrap();
        tx.send(2).unwrap();
        after_tx.send(()).unwrap();
        tx.send(3).unwrap();
    });
    entered_rx.recv_timeout(LIMIT).unwrap();
    // Channel contains item 1; no consumer has freed capacity.
    assert!(after_rx.try_recv().is_err());
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 1);
    after_rx.recv_timeout(LIMIT).unwrap();
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 2);
    assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 3);
    timer.join().unwrap();
}

#[test]
fn fixed_single_dispatcher_cannot_run_its_queued_dependency() {
    let (tx, rx) = mpsc::channel::<u32>();
    let (entered_tx, entered_rx) = mpsc::channel();
    let (release_tx, release_rx) = mpsc::channel();
    let (done_tx, done_rx) = mpsc::channel();
    let worker = thread::spawn(move || {
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 1);
        entered_tx.send(()).unwrap();
        // Represents callback 1 waiting for callback 2. The harness releases
        // it instead of letting the deliberately insufficient policy hang.
        release_rx.recv_timeout(LIMIT).unwrap();
        assert_eq!(rx.recv_timeout(LIMIT).unwrap(), 2);
        done_tx.send(2).unwrap();
    });
    tx.send(1).unwrap();
    entered_rx.recv_timeout(LIMIT).unwrap();
    tx.send(2).unwrap();
    assert!(done_rx.try_recv().is_err());
    release_tx.send(()).unwrap();
    assert_eq!(done_rx.recv_timeout(LIMIT).unwrap(), 2);
    worker.join().unwrap();
}

#[test]
fn full_try_send_returns_ownership_and_preserves_payload() {
    let (tx, rx) = mpsc::sync_channel(1);
    let first = Arc::new(1);
    let second = Arc::new(2);
    let weak = Arc::downgrade(&second);
    tx.send(first).unwrap();
    let returned = match tx.try_send(second) {
        Err(mpsc::TrySendError::Full(value)) => value,
        other => panic!("expected full, got {:?}", other),
    };
    assert!(weak.upgrade().is_some());
    assert_eq!(*returned, 2);
    assert_eq!(*rx.recv_timeout(LIMIT).unwrap(), 1);
    tx.try_send(returned).unwrap();
    let delivered = rx.recv_timeout(LIMIT).unwrap();
    assert_eq!(*delivered, 2);
    drop(delivered);
    assert!(weak.upgrade().is_none());
}

#[test]
fn disconnected_try_send_returns_payload_not_success() {
    let (tx, rx) = mpsc::sync_channel(1);
    drop(rx);
    let owner = Arc::new(7);
    let weak = Arc::downgrade(&owner);
    let returned = match tx.try_send(owner) {
        Err(mpsc::TrySendError::Disconnected(value)) => value,
        other => panic!("expected disconnect, got {:?}", other),
    };
    assert!(weak.upgrade().is_some());
    assert_eq!(*returned, 7);
    drop(returned);
    assert!(weak.upgrade().is_none());
}

// Explicit overflow ledger for a fixed synthetic workload. The overflow
// queue is not a production choice; it demonstrates that lossless nonblocking
// handoff can relocate a backlog rather than bound it.
#[test]
fn overflow_retains_due_tasks_and_accounts_for_all_stages() {
    const TOTAL: usize = 32;
    let (tx, rx) = mpsc::sync_channel(2);
    let mut pending: VecDeque<_> = (0..TOTAL).collect();
    let mut overflow = VecDeque::new();
    let mut ready = 0;
    let mut active = 0;
    let mut finished = Vec::new();
    while let Some(id) = pending.pop_front() {
        match tx.try_send(id) {
            Ok(()) => ready += 1,
            Err(mpsc::TrySendError::Full(id)) => overflow.push_back(id),
            Err(mpsc::TrySendError::Disconnected(_)) => panic!("unexpected disconnect"),
        }
        assert_eq!(pending.len() + overflow.len() + ready + active + finished.len(), TOTAL);
    }
    assert_eq!((ready, overflow.len()), (2, 30));
    while ready > 0 || !overflow.is_empty() {
        let id = rx.recv_timeout(LIMIT).unwrap();
        ready -= 1;
        active += 1;
        assert_eq!(pending.len() + overflow.len() + ready + active + finished.len(), TOTAL);
        if let Some(next) = overflow.pop_front() {
            tx.try_send(next).unwrap();
            ready += 1;
        }
        active -= 1;
        finished.push(id);
        assert_eq!(pending.len() + overflow.len() + ready + active + finished.len(), TOTAL);
    }
    assert_eq!(finished, (0..TOTAL).collect::<Vec<_>>());
}
