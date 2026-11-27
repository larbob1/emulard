# P02 — paired benchmark input integrity

Use independently collected logs from matched workloads, not copies of the
same run. benchmark_pairs.py now rejects repeated resolved paths and repeated
SHA-256 digests of the exact decoded text consumed by the report parser
(across baseline and candidate and all pairs). Universal newline conversion
and a missing final newline are normalized; decoding replacement may
conservatively reject distinct invalid-byte files with the same decoded text.
Warmup lines are included in the fingerprint. File size/mtime/ctime are
checked before and after the read to reject common concurrent-log changes;
this is not a filesystem snapshot or adversarial modification detector.
Keep logs closed before analysis.

    python3 tools/benchmark_pairs.py --pair baseline1.log candidate1.log --pair baseline2.log candidate2.log --pair baseline3.log candidate3.log --skip 5 --skip-frame-batches 1 --target-fps 30

Only reviewed numeric summaries go into coordination. Hashes, input paths and
raw log lines are not emitted. Exit 1 with repeated_log_content,
repeated_input_path or input_changed_during_read means the run set was
rejected. A successful result counts distinct normalized log contents, not
verified independent trials; even different log headers can mask reused
measurements. Match scene, resolution, flags, build, cache state, warmup,
duration and workload independently. Both independent_trials_verified and
matched_workload_verified remain false. Operator scene confirmation is not
a correctness guarantee or a visible FPS measurement. Use gameplay acceptance
for the formal milestone and keep the original working executable intact.
