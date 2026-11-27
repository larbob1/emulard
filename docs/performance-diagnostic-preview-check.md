# Diagnostic exact prepared preview check

Coordinator-owned review-only CI checks exact dirty proposal #28 41e4cbf5 against #23 c074896b, CPU proposal #15 e029744d against #18 dbac4c6. Fresh separate checkouts, pinned source prep, run existing in-memory previews, reject missing/duplicate anchors or empty diff; compare tracked diff/status before and after. No proposed source applied, no native compile or runtime registration. This checks exact prepared anchors only, not caller-held locks, feature graph, log I/O, actual behavior or performance. No title data or private logs.
