// SPDX-License-Identifier: GPL-3.0-or-later
//! Scratch-only child tests. The external parent owns the terminal receipt.
use super::*;
use std::sync::atomic::{AtomicU32, AtomicUsize};
use windows_sys::Win32::System::Memory::{MapViewOfFile, OpenFileMappingW, FILE_MAP_WRITE};

const RECEIPT_ENV: &str = "AI6_TERMINAL_RECEIPT_NAME";
const MAGIC: u32 = 0x4136_4254;
const COMMITTED: u32 = 0x434F_4D54;
static VIEW: AtomicUsize = AtomicUsize::new(0);

#[repr(C)]
struct Receipt {
    magic: AtomicU32,
    count: AtomicU32,
    lifecycle: AtomicU32,
    reason: AtomicU32,
    commit: AtomicU32,
    reserved: [AtomicU32; 3],
}

fn attach_receipt() {
    let name = std::env::var(RECEIPT_ENV).expect("parent receipt mapping name");
    assert!(!name.is_empty() && name.starts_with("Local\\ai6-terminal-"));
    let wide: Vec<u16> = name.encode_utf16().chain([0]).collect();
    assert!(!wide[..wide.len() - 1].contains(&0));
    // SAFETY: null-terminated name; parent owns a fresh 32-byte mapping.
    let handle = unsafe { OpenFileMappingW(FILE_MAP_WRITE, 0, wide.as_ptr()) };
    assert!(!handle.is_null(), "open parent mapping");
    // SAFETY: valid handle; only the fixed receipt extent is accessed.
    let mapped = unsafe { MapViewOfFile(handle, FILE_MAP_WRITE, 0, 0, 32) };
    let address = mapped.Value as usize;
    assert_ne!(address, 0);
    assert_eq!(address % std::mem::align_of::<Receipt>(), 0);
    assert_eq!(std::mem::size_of::<Receipt>(), 32);
    // SAFETY: aligned initialized parent mapping, held through child exit.
    let receipt = unsafe { &*(address as *const Receipt) };
    assert_eq!(receipt.magic.load(Ordering::Acquire), MAGIC);
    assert_eq!(receipt.count.load(Ordering::Acquire), 0);
    assert_eq!(receipt.lifecycle.load(Ordering::Acquire), 0);
    assert_eq!(receipt.reason.load(Ordering::Acquire), 0);
    assert_eq!(receipt.commit.load(Ordering::Acquire), 0);
    assert!(receipt.reserved.iter().all(|word| word.load(Ordering::Acquire) == 0));
    assert_eq!(VIEW.swap(address, Ordering::AcqRel), 0);
    // Mapping and handle intentionally remain valid through process exit.
}

// Invoked only in scratch cfg(test), immediately before real TerminateProcess.
pub(super) fn observe_boundary(state: &State) {
    let address = VIEW.load(Ordering::Acquire);
    if address == 0 {
        return; // No observation; parent must reject absent receipt.
    }
    // SAFETY: attach_receipt published a process-lifetime aligned mapping.
    let receipt = unsafe { &*(address as *const Receipt) };
    receipt.count.fetch_add(1, Ordering::AcqRel);
    receipt.lifecycle.store(u32::from(state.lifecycle.load(Ordering::Acquire)), Ordering::Relaxed);
    receipt.reason.store(u32::from(state.reason.load(Ordering::Acquire)), Ordering::Relaxed);
    receipt.commit.store(COMMITTED, Ordering::Release);
}

#[test]
#[ignore = "fresh isolated child required"]
fn actual_prearm() {
    assert!(std::env::var_os(RECEIPT_ENV).is_none());
    let first = prearm().expect("actual supervisor prearm");
    let second = prearm().expect("repeat prearm");
    assert!(std::ptr::eq(first, second));
    assert_eq!(first.0.lifecycle.load(Ordering::Acquire), ARMED);
    assert_eq!(first.0.reason.load(Ordering::Acquire), 0);
    assert!(!first.0.wake_failed.load(Ordering::Acquire));
    assert!(!first.0.park_failed.load(Ordering::Acquire));
    eprintln!("ai6_terminal_startup same=1 armed=1 reason=0 wake_failed=0 park_failed=0");
}

#[test]
#[ignore = "fresh isolated terminating child required"]
fn actual_terminal() {
    attach_receipt();
    let token = prearm().expect("actual supervisor prearm");
    assert_eq!(token.0.lifecycle.load(Ordering::Acquire), ARMED);
    assert_eq!(token.0.reason.load(Ordering::Acquire), 0);
    token.request_stop(Reason::PublicationUnresolved);
}
