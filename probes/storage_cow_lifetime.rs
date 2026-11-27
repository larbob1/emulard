// SPDX-License-Identifier: GPL-3.0-or-later
//! Standalone P23 review probe. Actual Rust Cow shadow/drop semantics;
//! synthetic transforms only, not victory-hle, real codecs, host mappings,
//! allocator accounting or runtime instrumentation.
use std::{borrow::Cow, cell::Cell, rc::Rc};

#[derive(Clone)]
struct Byte {
    value: u8,
    dropped: Option<Rc<Cell<usize>>>,
}

impl Drop for Byte {
    fn drop(&mut self) {
        if let Some(count) = &self.dropped {
            count.set(count.get() + 1);
        }
    }
}

fn tracked(values: &[u8], dropped: &Rc<Cell<usize>>) -> Vec<Byte> {
    values.iter().map(|&value| Byte {
        value,
        dropped: Some(Rc::clone(dropped)),
    }).collect()
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Failure { Inflate, Decode }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Phase { Intermediate, Decode, Retry, Publish }

// Preserve the actual execute() shadowing and conditional move structure.
// Output transform is intentionally fake. Drop-count tokens do not measure
// allocator bytes, capacity, RSS, or deallocation latency.
fn execute_model(
    source: Cow<'_, [Byte]>,
    chained: bool,
    early_drop: bool,
    failure: Option<Failure>,
    retries: usize,
    mut observe: impl FnMut(Phase),
) -> Result<Vec<u8>, Failure> {
    let source = if chained {
        let mut packed: Vec<Byte> = source.iter().map(|b| Byte {
            value: b.value ^ 0x55,
            dropped: None,
        }).collect();
        observe(Phase::Intermediate);
        if failure == Some(Failure::Inflate) {
            return Err(Failure::Inflate);
        }
        // A deliberately short successful first-stage decode.
        packed.truncate(packed.len().saturating_sub(1));
        if early_drop {
            drop(source);
        }
        Cow::Owned(packed)
    } else {
        source
    };
    observe(Phase::Decode);
    if failure == Some(Failure::Decode) {
        return Err(Failure::Decode);
    }
    let output: Vec<u8> = source.iter().map(|b| b.value.wrapping_add(1)).collect();
    for _ in 0..retries {
        observe(Phase::Retry);
    }
    observe(Phase::Publish);
    Ok(output)
}

#[test]
fn shadow_retains_owned_source_until_scope_exit() {
    let dropped = Rc::new(Cell::new(0));
    let source = Cow::Owned(tracked(&[1, 2, 3, 4], &dropped));
    let result = execute_model(source, true, false, None, 3, |_| {
        assert_eq!(dropped.get(), 0);
    });
    assert_eq!(result, Ok(vec![0x55, 0x58, 0x57]));
    assert_eq!(dropped.get(), 4);
}

#[test]
fn explicit_drop_precedes_decode_and_retries() {
    let dropped = Rc::new(Cell::new(0));
    let source = Cow::Owned(tracked(&[1, 2, 3, 4], &dropped));
    let mut phases = Vec::new();
    let result = execute_model(source, true, true, None, 3, |phase| {
        phases.push(phase);
        assert_eq!(dropped.get(), if phase == Phase::Intermediate { 0 } else { 4 });
    });
    assert_eq!(result, Ok(vec![0x55, 0x58, 0x57]));
    assert_eq!(phases, vec![Phase::Intermediate, Phase::Decode, Phase::Retry,
                            Phase::Retry, Phase::Retry, Phase::Publish]);
    assert_eq!(dropped.get(), 4);
}

#[test]
fn borrowed_source_is_not_destroyed() {
    for early in [false, true] {
        let dropped = Rc::new(Cell::new(0));
        let original = tracked(&[1, 2, 3, 4], &dropped);
        let result = execute_model(Cow::Borrowed(&original), true, early, None, 1, |_| {
            assert_eq!(dropped.get(), 0);
        });
        assert_eq!(result, Ok(vec![0x55, 0x58, 0x57]));
        assert_eq!(original[3].value, 4);
        assert_eq!(dropped.get(), 0);
        drop(original);
        assert_eq!(dropped.get(), 4);
    }
}

#[test]
fn nonchained_retains_source_in_both_modes() {
    for early in [false, true] {
        let dropped = Rc::new(Cell::new(0));
        let result = execute_model(Cow::Owned(tracked(&[1, 2, 3, 4], &dropped)),
                                   false, early, None, 1, |_| {
            assert_eq!(dropped.get(), 0);
        });
        assert_eq!(result, Ok(vec![2, 3, 4, 5]));
        assert_eq!(dropped.get(), 4);
    }
}

#[test]
fn failed_first_stage_drops_once_without_publication() {
    for early in [false, true] {
        let dropped = Rc::new(Cell::new(0));
        let mut phases = Vec::new();
        let result = execute_model(Cow::Owned(tracked(&[1, 2, 3, 4], &dropped)),
                                   true, early, Some(Failure::Inflate), 0, |phase| {
            phases.push(phase);
            assert_eq!(dropped.get(), 0);
        });
        assert_eq!(result, Err(Failure::Inflate));
        assert_eq!(phases, vec![Phase::Intermediate]);
        assert_eq!(dropped.get(), 4);
    }
}

#[test]
fn failed_second_stage_drops_once_without_publication() {
    for early in [false, true] {
        let dropped = Rc::new(Cell::new(0));
        let mut phases = Vec::new();
        let result = execute_model(Cow::Owned(tracked(&[1, 2, 3, 4], &dropped)),
                                   true, early, Some(Failure::Decode), 0, |phase| {
            phases.push(phase);
            assert_eq!(dropped.get(), if early && phase == Phase::Decode { 4 } else { 0 });
        });
        assert_eq!(result, Err(Failure::Decode));
        assert_eq!(phases, vec![Phase::Intermediate, Phase::Decode]);
        assert_eq!(dropped.get(), 4);
    }
}

#[test]
fn empty_and_short_outputs_match() {
    for input in [&[][..], &[42][..], &[1, 2][..]] {
        let run = |early| {
            let dropped = Rc::new(Cell::new(0));
            let result = execute_model(Cow::Owned(tracked(input, &dropped)),
                                       true, early, None, 0, |_| {});
            assert_eq!(dropped.get(), input.len());
            result
        };
        assert_eq!(run(false), run(true));
        assert_eq!(run(true).unwrap().len(), input.len().saturating_sub(1));
    }
}
