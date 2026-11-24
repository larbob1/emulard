# Packed-byte shader operations

The pinned runtime decodes v_dot4_i32_i8 and v_dot4_u32_u8 but does not lower them. Marvisak/VIctory implements the signed form. The independent Five Star Recomp translator was searched for these exact opcode names, with no matches.

This candidate implements non-saturating packed forms using integer arithmetic with explicit half selection, byte extraction, sign or zero extension and wrapping accumulation. Unverified modifiers remain unsupported. The implicit-destination and signed 64-bit multiply-add forms need separate review.

The CI workflow runs the synthetic lowering test; the GPU reference test is available separately. No new shader coverage count, correct lighting or performance result is claimed. The existing builder safety gate remains unchanged.
