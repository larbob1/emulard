# Reverse alias index refresh

P05/P08: port the earlier 3b63d02 experiment to current cumulative source.
Both HLE and GPU reverse indexes store unique virtual addresses in BTreeSet
rather than vectors. Removing one mapping changes from a linear retain scan
to a logarithmic set removal for that physical page. It does not change
the host mappings, dirty notification ownership, or GPU synchronization.
Consumers that need vectors still construct them; existing address-order
sort/coalesce logic remains. For common singleton/small alias sets, tree
allocation and insertion can cost more than Vec. Treat this unconditional
data-structure change as isolated candidate, not a new cumulative default.

The new HLE native fixture creates 64 aliases of one physical page,
remaps half to a different page, checks exact reverse-index contents and
actual alias bytes, then unmaps all views and frees IDs. GPU fixture checks
independent views and removal. Both build profiles and existing map/replay
fixtures are required. No gameplay speedup claimed. Benchmark actual alias
group sizes, map/unmap time and reader wait before integration.
