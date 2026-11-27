## Isolated P16 extent-validation snapshot

Child of exact native-validated #23 c074896b. Two exact source/test blobs from AI2 #17 f103fcf5 (delta from 5e4aabec); prior blob identities match. No other runtime changes. Validate all eight pipeline_stream_ tests, both shader ownership cases, retained four copy-back modes and both profiles. Arithmetic extent checks do not establish arbitrary pointer readability or resolve historical shader translation errors. Native/Proton validation pending; no merge, no measured FPS improvement.
