# Reverse-alias index candidate

This isolated branch builds on Phase 6 but does not change the main
performance candidate while its Windows regression suite runs.

It ports the BTreeSet reverse alias indexing portion of the existing
fxceless streaming-page-aliases patch to paired-wave. Both HLE and GPU
reverse maps now store unique virtual page addresses. Removing one alias
uses an ordered-set lookup rather than scanning all aliases of that
physical page. The GPU copy-back path also checks the alias count before
allocating its returned vector. Consumers that group address ranges
already sort them; guard consumers traverse the same set, now in address
order.

This changes the index representation on this branch; it is not enabled
on the cumulative Phase 6 branch. The asymptotic improvement for large
alias sets is not a measured FPS improvement: tree allocation and
iteration may cost more for small groups. Benchmark both variants on
the same workload, and validate alias writes, remap refusal, tile replay,
and the added renderer reverse-index regression. Only merge after
Windows/Proton and rendering checks pass.

P05/P08/P18 remain unresolved. This does not implement placeholder
interval tracking, software GPU page tables or lifetime-pinned sections.
