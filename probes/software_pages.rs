// SPDX-License-Identifier: GPL-3.0-or-later
//! Pure software mapping model. No host pointers, mappings, or GPU work.
//! Section keys are logical identities, NOT native handle values.
use std::collections::BTreeMap;

pub const PAGE_BYTES: usize = 64 * 1024;
const MAX_OPERATION_PAGES: usize = 65_536;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct SectionKey {
    pub id: u64,
    pub generation: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Page {
    section: SectionKey,
    index: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Span {
    pub section: SectionKey,
    pub offset: usize,
    pub len: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    Overflow,
    TooLarge,
    Hole,
    MissingBacking,
}

#[derive(Default)]
pub struct PageTable {
    pages: BTreeMap<usize, Page>,
}

fn checked_range(first: usize, count: usize) -> Result<std::ops::Range<usize>, Error> {
    if count > MAX_OPERATION_PAGES { return Err(Error::TooLarge); }
    let end = first.checked_add(count).ok_or(Error::Overflow)?;
    if count != 0 {
        end.checked_mul(PAGE_BYTES).ok_or(Error::Overflow)?;
    }
    Ok(first..end)
}

impl PageTable {
    // All arithmetic is checked before mutating the table.
    pub fn map(&mut self, destination: usize, count: usize, section: SectionKey, first: usize) -> Result<(), Error> {
        let dst = checked_range(destination, count)?;
        let src = checked_range(first, count)?;
        for (at, index) in dst.zip(src) {
            self.pages.insert(at, Page { section, index });
        }
        Ok(())
    }

    pub fn unmap(&mut self, destination: usize, count: usize) -> Result<(), Error> {
        for at in checked_range(destination, count)? { self.pages.remove(&at); }
        Ok(())
    }

    // Snapshot semantics for the model. Production overlap/partial-source
    // behavior must be audited separately; do not replace map_alias with this.
    pub fn alias_complete(&mut self, destination: usize, source: usize, count: usize) -> Result<(), Error> {
        let dst = checked_range(destination, count)?;
        let src = checked_range(source, count)?;
        let plan: Vec<Page> = src.map(|at| self.pages.get(&at).copied().ok_or(Error::Hole))
            .collect::<Result<_, _>>()?;
        for (at, page) in dst.zip(plan) { self.pages.insert(at, page); }
        Ok(())
    }

    // No raw title pointers are returned. Coalesce only adjacent bytes in
    // the same logical section generation. A hole fails the entire plan.
    pub fn resolve(&self, address: usize, len: usize) -> Result<Vec<Span>, Error> {
        let end = address.checked_add(len).ok_or(Error::Overflow)?;
        if len == 0 { return Ok(Vec::new()); }
        if (end - 1) / PAGE_BYTES - address / PAGE_BYTES >= MAX_OPERATION_PAGES {
            return Err(Error::TooLarge);
        }
        let mut out: Vec<Span> = Vec::new();
        let mut at = address;
        while at < end {
            let page = self.pages.get(&(at / PAGE_BYTES)).ok_or(Error::Hole)?;
            let within = at % PAGE_BYTES;
            let count = (PAGE_BYTES - within).min(end - at);
            let offset = page.index.checked_mul(PAGE_BYTES)
                .and_then(|base| base.checked_add(within)).ok_or(Error::Overflow)?;
            if let Some(last) = out.last_mut()
                && last.section == page.section
                && last.offset.checked_add(last.len) == Some(offset)
            {
                last.len = last.len.checked_add(count).ok_or(Error::Overflow)?;
            } else {
                out.push(Span { section: page.section, offset, len: count });
            }
            at += count;
        }
        Ok(out)
    }

    // The supplied backing slices are borrowed for this call. Validate
    // every span before copying so a hole or missing section leaves out
    // unchanged. This models a pinned reader, not actual section lifetime.
    pub fn read<'a>(&self, address: usize, out: &mut [u8], backing: impl Fn(SectionKey) -> Option<&'a [u8]>) -> Result<(), Error> {
        let plan = self.resolve(address, out.len())?;
        let mut slices = Vec::with_capacity(plan.len());
        for span in plan {
            let end = span.offset.checked_add(span.len).ok_or(Error::Overflow)?;
            let bytes = backing(span.section).and_then(|b| b.get(span.offset..end)).ok_or(Error::MissingBacking)?;
            slices.push(bytes);
        }
        let mut done = 0;
        for bytes in slices {
            out[done..done + bytes.len()].copy_from_slice(bytes);
            done += bytes.len();
        }
        Ok(())
    }
}

#[cfg(test)]
mod software_page_tests {
    use super::*;
    const A: SectionKey = SectionKey { id: 7, generation: 1 };
    const B: SectionKey = SectionKey { id: 7, generation: 2 };
    #[test]
    fn coalesces_exact_backing_and_splits_other_generations() {
        let mut t = PageTable::default();
        t.map(4, 2, A, 2).unwrap();
        t.map(6, 1, B, 4).unwrap();
        assert_eq!(t.resolve(5*PAGE_BYTES-3, PAGE_BYTES+9).unwrap(), vec![
            Span { section:A, offset:3*PAGE_BYTES-3, len:PAGE_BYTES+3 },
            Span { section:B, offset:4*PAGE_BYTES, len:6 }
        ]);
    }
    #[test]
    fn aliases_read_current_bytes_and_scattered_boundaries() {
        let mut t = PageTable::default();
        t.map(0, 1, A, 1).unwrap();
        t.map(1, 1, A, 0).unwrap();
        t.alias_complete(2, 0, 2).unwrap();
        let mut backing = vec![3; PAGE_BYTES*2];
        backing[PAGE_BYTES..].fill(9);
        let mut out = [0; 4];
        t.read(3*PAGE_BYTES-2, &mut out, |k| (k==A).then_some(backing.as_slice())).unwrap();
        assert_eq!(out, [9,9,3,3]);
        backing[2*PAGE_BYTES-1] = 8;
        t.read(PAGE_BYTES-2, &mut out, |k| (k==A).then_some(backing.as_slice())).unwrap();
        assert_eq!(out, [9,8,3,3]);
    }
    #[test]
    fn holes_and_missing_backing_do_not_change_output() {
        let mut t = PageTable::default();
        t.map(0, 1, A, 0).unwrap();
        let backing = vec![1; PAGE_BYTES];
        let mut out = [42; 4];
        assert_eq!(t.read(PAGE_BYTES-2, &mut out, |_| Some(backing.as_slice())), Err(Error::Hole));
        assert_eq!(out, [42;4]);
        t.map(1, 1, B, 0).unwrap();
        assert_eq!(t.read(PAGE_BYTES-2, &mut out, |k| (k==A).then_some(backing.as_slice())), Err(Error::MissingBacking));
        assert_eq!(out, [42;4]);
        t.unmap(0, 1).unwrap();
        assert_eq!(t.resolve(0, 1), Err(Error::Hole));
    }
    #[test]
    fn overlap_snapshot_and_failed_alias_are_atomic_in_model() {
        let mut t = PageTable::default();
        t.map(0, 3, A, 0).unwrap();
        t.alias_complete(1, 0, 3).unwrap();
        assert_eq!(t.resolve(PAGE_BYTES, 3*PAGE_BYTES).unwrap(), vec![Span { section:A, offset:0, len:3*PAGE_BYTES }]);
        let before = t.resolve(0, 4*PAGE_BYTES).unwrap();
        assert_eq!(t.alias_complete(0, 3, 2), Err(Error::Hole));
        assert_eq!(t.resolve(0, 4*PAGE_BYTES).unwrap(), before);
    }
    #[test]
    fn rejects_overflow_and_excessive_requests() {
        let mut t = PageTable::default();
        assert_eq!(t.map(usize::MAX, 1, A, 0), Err(Error::Overflow));
        assert_eq!(t.map(0, 1, A, usize::MAX), Err(Error::Overflow));
        assert_eq!(t.map(0, MAX_OPERATION_PAGES+1, A, 0), Err(Error::TooLarge));
        assert_eq!(t.resolve(usize::MAX, 2), Err(Error::Overflow));
        assert_eq!(t.resolve(usize::MAX, 0), Ok(vec![]));
    }
    #[test]
    fn deterministic_remaps_match_dense_reference() {
        let mut t = PageTable::default();
        let mut dense = [None; 32];
        let mut seed = 17u32;
        for _ in 0..1000 {
            seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
            let dst = ((seed >> 8) % 32) as usize;
            let src = ((seed >> 16) % 16) as usize;
            if seed & 3 == 0 {
                t.unmap(dst,1).unwrap();
                dense[dst] = None;
            } else {
                let section = if seed & 4 == 0 { A } else { B };
                t.map(dst,1,section,src).unwrap();
                dense[dst] = Some(Span { section, offset:src*PAGE_BYTES, len:PAGE_BYTES });
            }
            for (slot, expected) in dense.iter().enumerate() {
                assert_eq!(t.resolve(slot*PAGE_BYTES,PAGE_BYTES), expected.map(|span| vec![span]).ok_or(Error::Hole));
            }
        }
    }
}
