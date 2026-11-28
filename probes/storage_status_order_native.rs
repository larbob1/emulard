    // SPDX-License-Identifier: GPL-3.0-or-later
    // Scheduler-only witnesses. No actual worker, I/O, or page-list access.
    fn order_marker(l: &mut Lanes, array: Array, index: u32) {
        let status = Status { array, index };
        add_ref_instance(array);
        status.entry().store(E_PENDING, Ordering::Release);
        l.lanes.get_mut(&0).unwrap().unsubmitted.push(Command::Status(status));
    }

    fn order_snapshot(
        l: &Lanes, array: Array, phases: &mut u32,
        held: &[u32], reads: &[(u64, u64)], running: &[u64],
        markers: &[(u64, u32)], failures: &[(u64, HRESULT)],
        staged: u64, refs: u32, values: &[HRESULT],
    ) {
        assert_eq!(l.lanes.len(), 1);
        let lane = &l.lanes[&0];
        assert!(!lane.closed);
        assert_eq!(lane.capacity, 6);
        assert!(lane.unsubmitted.is_empty());
        let actual_held: Vec<u32> = lane.held.iter().map(|command| match command {
            Command::Read(r) => {
                assert_eq!(r.options, PAGE_DESTINATION);
                assert_eq!((r.source_size, r.destination_size), (16, 16));
                0
            }
            Command::Status(s) => {
                assert_eq!(s.array, array);
                assert_eq!(s.index, 0);
                1
            }
        }).collect();
        let actual_reads: Vec<_> = lane.reads.iter().map(|(seq, r)| {
            assert_eq!((r.source_size, r.destination_size), (16, 16));
            (*seq, r.options)
        }).collect();
        let actual_running: Vec<_> = lane.running.iter().copied().collect();
        let actual_markers: Vec<_> = lane.statuses.iter().map(|(seq, s)| {
            assert_eq!(s.array, array);
            (*seq, s.index)
        }).collect();
        let actual_failures: Vec<_> = lane.failures.iter().map(|(seq, hr)| (*seq, *hr)).collect();
        assert_eq!(actual_held.as_slice(), held);
        assert_eq!(actual_reads.as_slice(), reads);
        assert_eq!(actual_running.as_slice(), running);
        assert_eq!(actual_markers.as_slice(), markers);
        assert_eq!(actual_failures.as_slice(), failures);
        assert_eq!(l.staged, staged);
        assert_eq!(unsafe { &*array }.refs.load(Ordering::Acquire), refs);
        for (i, value) in values.iter().enumerate() {
            assert_eq!(result(array.cast(), i as u32), *value);
        }
        *phases += 1;
    }

    fn order_case(mode: u32) {
        assert!(mode <= 2);
        let cross = mode == 2;
        let mut l = lanes(STAGING);
        l.lanes.insert(0, Lane::new(0, 6));
        let markers = if cross { 2 } else { 1 };
        let array = status_array(markers).cast::<Instance<StatusArray>>();
        assert!(!array.is_null());
        assert_eq!(unsafe { &*array }.refs.load(Ordering::Acquire), 1);
        let mut phases = 0;
        read(&mut l, 0, PAGE_DESTINATION, 16);
        if cross { order_marker(&mut l, array, 0); }
        read(&mut l, 0, 0, 16);
        if !cross { order_marker(&mut l, array, 0); }
        assert_eq!(l.lanes[&0].unsubmitted.len(), 3);
        l.submit_as(0, false);
        order_snapshot(&l, array, &mut phases, &[0, 1], &[(0, 0)], &[], &[], &[], 0, 2, &[E_PENDING]);
        let ordinary = l.start().unwrap();
        assert_eq!((ordinary.lane, ordinary.seq, ordinary.request.options, ordinary.staging), (0, 0, 0, 0));
        order_snapshot(&l, array, &mut phases, &[0, 1], &[], &[0], &[], &[], 0, 2, &[E_PENDING]);
        assert!(l.start().is_none());
        let ordinary_error = if mode == 0 { S_OK } else { END_OF_FILE };
        let page_error = if mode == 1 { INVALID_DATA } else { S_OK };
        let ordinary_result = if ordinary_error == S_OK { Ok(()) } else { Err(ordinary_error) };
        let page_result = if page_error == S_OK { Ok(()) } else { Err(page_error) };
        let early_failure = [(0, END_OF_FILE)];
        let prior: &[(u64, HRESULT)] = if mode == 1 { &early_failure } else { &[] };
        if !cross {
            l.finish(&ordinary, ordinary_result);
            order_snapshot(&l, array, &mut phases, &[0, 1], &[], &[], &[], prior, 0, 2, &[E_PENDING]);
        } else {
            order_marker(&mut l, array, 1);
            assert_eq!(l.lanes[&0].unsubmitted.len(), 1);
        }
        l.submit(0);
        let two_markers = [(2, 0), (3, 1)];
        let one_marker = [(2, 0)];
        let expected_markers: &[(u64, u32)] = if cross { &two_markers } else { &one_marker };
        let waiting: &[u64] = if cross { &[0] } else { &[] };
        let pending: &[HRESULT] = if cross { &[E_PENDING, E_PENDING] } else { &[E_PENDING] };
        let refs = if cross { 3 } else { 2 };
        order_snapshot(&l, array, &mut phases, &[], &[(1, PAGE_DESTINATION)], waiting, expected_markers, prior, 0, refs, pending);
        let page = l.start().unwrap();
        assert_eq!((page.lane, page.seq, page.request.options, page.staging), (0, 1, PAGE_DESTINATION, 16));
        let active: &[u64] = if cross { &[0, 1] } else { &[1] };
        order_snapshot(&l, array, &mut phases, &[], &[], active, expected_markers, prior, 16, refs, pending);
        l.finish(&page, page_result);
        let after_page_m0 = result(array.cast(), 0);
        if cross {
            order_snapshot(&l, array, &mut phases, &[], &[], &[0], expected_markers, &[], 0, 3, pending);
            l.finish(&ordinary, ordinary_result);
        }
        let m0 = result(array.cast(), 0);
        let m1 = if cross { result(array.cast(), 1) } else { E_PENDING };
        let actual_final: &[HRESULT] = if cross { &[END_OF_FILE, S_OK] } else if mode == 1 { &[END_OF_FILE] } else { &[S_OK] };
        order_snapshot(&l, array, &mut phases, &[], &[], &[], &[], &[], 0, 1, actual_final);
        let expected_m0 = if cross || page_error != S_OK { page_error } else { ordinary_error };
        let expected_m1 = if cross { ordinary_error } else { E_PENDING };
        if mode == 0 {
            assert_eq!((m0, m1), (expected_m0, expected_m1));
        } else {
            assert_ne!(m0, expected_m0);
            if cross {
                assert_ne!(m1, expected_m1);
                assert_eq!(after_page_m0, E_PENDING);
            }
        }
        assert_eq!(phases, 6);
        assert_eq!(l.next_seq, if cross { 4 } else { 3 });
        assert!(!l.starved);
        assert_eq!(l.refused, 0);
        l.lanes.remove(&0).unwrap();
        assert!(l.lanes.is_empty());
        assert_eq!(l.staged, 0);
        let released = release(array);
        assert_eq!(released, 0);
        // No access to the array after its final release.
        eprintln!("storage_status_order mode={} phases={} markers={} page_result={:08x} ordinary_result={:08x} after_page_m0={:08x} m0={:08x} m1={:08x} expected_m0={:08x} expected_m1={:08x} lanes={} staged={} released={}",
            mode, phases, markers, page_error, ordinary_error, after_page_m0,
            m0, m1, expected_m0, expected_m1, l.lanes.len(), l.staged, released);
    }

    #[test]
    #[ignore = "isolated scheduler ordering positive control"]
    fn storage_status_order_b0() { order_case(0); }

    #[test]
    #[ignore = "isolated scheduler first-error baseline witness"]
    fn storage_status_order_b1() { order_case(1); }

    #[test]
    #[ignore = "isolated scheduler cross-marker baseline witness"]
    fn storage_status_order_b2() { order_case(2); }
