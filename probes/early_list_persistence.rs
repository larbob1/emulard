// SPDX-License-Identifier: GPL-3.0-or-later
//! Review-only early-list persistence model; no filesystem or driver calls.
//! Authorization is supplied by the caller, not established by this model.

use std::collections::BTreeSet;
use std::sync::{Mutex, TryLockError};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Save {
    Denied,
    Busy,
    Clean,
    Saved,
    Failed,
}

#[derive(Default)]
struct State {
    keys: BTreeSet<String>,
    dirty: bool,
}

#[derive(Default)]
struct EarlyList {
    state: Mutex<State>,
    save_gate: Mutex<()>,
}

impl EarlyList {
    fn note(&self, key: &str) {
        let mut state = self.state.lock().unwrap();
        if state.keys.insert(key.to_owned()) {
            state.dirty = true;
        }
    }

    // Only a reviewed owner with allowed cache policy may publish.
    // Library availability deliberately is not a prerequisite.
    fn save(&self, owner: bool, policy_allows: bool,
            publish: impl FnOnce(&[String]) -> bool) -> Save {
        if !owner || !policy_allows {
            return Save::Denied;
        }
        let _gate = match self.save_gate.try_lock() {
            Ok(g) => g,
            Err(TryLockError::WouldBlock) => return Save::Busy,
            Err(TryLockError::Poisoned(_)) => return Save::Denied,
        };
        let keys = {
            let mut state = self.state.lock().unwrap();
            if !state.dirty {
                return Save::Clean;
            }
            let keys: Vec<_> = state.keys.iter().cloned().collect();
            state.dirty = false;
            keys
        };
        // A later note can run during publication, without a state lock.
        // In-flight dirty consumption is restored even during unwinding.
        struct Restore<'a> {
            state: &'a Mutex<State>,
            committed: bool,
        }
        impl Drop for Restore<'_> {
            fn drop(&mut self) {
                if !self.committed {
                    self.state.lock().unwrap_or_else(|e| e.into_inner()).dirty = true;
                }
            }
        }
        let mut restore = Restore { state: &self.state, committed: false };
        if publish(&keys) {
            restore.committed = true;
            Save::Saved
        } else {
            Save::Failed
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn denied_owner_or_policy_never_consumes_dirty() {
        let list = EarlyList::default();
        list.note("A");
        for (owner, policy) in [(false, true), (true, false), (false, false)] {
            assert_eq!(list.save(owner, policy, |_| panic!("denied publication")), Save::Denied);
        }
        assert_eq!(list.save(true, true, |keys| keys == ["A"]), Save::Saved);
    }

    #[test]
    fn failure_retries_same_keys_without_library() {
        let list = EarlyList::default();
        list.note("A");
        assert_eq!(list.save(true, true, |keys| { assert_eq!(keys, ["A"]); false }), Save::Failed);
        assert_eq!(list.save(true, true, |keys| keys == ["A"]), Save::Saved);
        assert_eq!(list.save(true, true, |_| panic!("clean publication")), Save::Clean);
    }

    #[test]
    fn concurrent_new_key_survives_success() {
        let list = EarlyList::default();
        list.note("A");
        assert_eq!(list.save(true, true, |keys| {
            assert_eq!(keys, ["A"]);
            list.note("B");
            true
        }), Save::Saved);
        assert_eq!(list.save(true, true, |keys| keys == ["A", "B"]), Save::Saved);
    }

    #[test]
    fn concurrent_new_key_survives_failure() {
        let list = EarlyList::default();
        list.note("A");
        assert_eq!(list.save(true, true, |keys| {
            assert_eq!(keys, ["A"]);
            list.note("B");
            false
        }), Save::Failed);
        assert_eq!(list.save(true, true, |keys| keys == ["A", "B"]), Save::Saved);
    }

    #[test]
    fn busy_save_does_not_consume_new_dirty() {
        let list = EarlyList::default();
        list.note("A");
        assert_eq!(list.save(true, true, |_| {
            list.note("B");
            assert_eq!(list.save(true, true, |_| panic!("busy publication")), Save::Busy);
            true
        }), Save::Saved);
        assert_eq!(list.save(true, true, |keys| keys == ["A", "B"]), Save::Saved);
    }

    #[test]
    fn duplicate_note_does_not_trigger_extra_write() {
        let list = EarlyList::default();
        list.note("A");
        assert_eq!(list.save(true, true, |_| { list.note("A"); true }), Save::Saved);
        assert_eq!(list.save(true, true, |_| panic!("duplicate publication")), Save::Clean);
    }

    #[test]
    fn unwind_restores_dirty_and_quarantines_gate() {
        let list = EarlyList::default();
        list.note("A");
        let result = std::panic::catch_unwind(|| list.save(true, true, |_| panic!("uncertain publication")));
        assert!(result.is_err());
        assert!(list.state.lock().unwrap().dirty);
        // A poisoned gate is not automatically retried after uncertain
        // publication; a future runtime recovery policy needs proof.
        assert_eq!(list.save(true, true, |_| panic!("quarantined publication")), Save::Denied);
    }
}
