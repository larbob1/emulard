# Signed wide multiply-add and first launch

Marvisak/VIctory lowers signed wide multiply-add using sign extension of the two 32-bit factors and a 64-bit sum with the addend. The candidate adapts that result path into the pinned baseline. The signed flag remains unsupported; its lane boolean is not fabricated. Unsupported signed modifiers are refused. The unsigned path preserves its original carry behavior.

A synthetic shader lowering regression checks both result dwords; a separate GPU reference test covers negative products, carry across the low dword and wrapping at the 64-bit boundary. The GPU test is not automatically executed by CI. The two shader source compositions were checked against the pinned blobs.

First-launch documentation now points to the fully compile-verified revision 71c8936, not the newer unverified candidate. Both configurations succeeded in runtime workflow 45515044086. Synthetic checks passed at a889da8, with its full validation still in progress at preparation time.

Marvisak's advanced inter-block range analysis and sparse residency architecture remain reference material rather than drop-in compatible runtime code. Five Star's dynamic compiler budget and independent graphics backend likewise need separate integration work. No complete builder, lighting, replay, writeback filter, Linux execution or frame-rate result is claimed.
