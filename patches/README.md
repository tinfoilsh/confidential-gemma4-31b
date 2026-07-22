# vLLM v0.25.1 Deployment Patches

These four patches apply in filename order to the official vLLM v0.25.1
Python package. They were generated from
`tinfoilsh/vllm-cc-opt:milestone/gemma4-cc-v0251-b300-20260722` at commit
`894b5f0f6f78c8b02663110be7998fa0dd2063f2`.

## Included

- `0101` allows this public deployment to reject user-provided regex
  constraints. The upstream compilation timeout remains in place.
- `0102` centralizes the pageable-host-staging policy at v0.25.1's global
  `PIN_MEMORY` hook. `VLLM_CC_PAGEABLE_H2D=1` avoids pinned staging in full CC.
- `0103` enables vLLM's repetition detector for grammar-constrained Gemma
  output while preserving an explicit all-zero caller opt-out.
- `0104` is upstream commit `b2b8f679d` (merged after v0.25.1). It restores
  target-width input embeddings for MTP drafts while retaining the EAGLE width
  guard. Without it, Gemma 4 MTP fails initialization with a 6400 x 10752
  projection mismatch.

## Removed From v0.23.0

The v0.23.0 Gemma streaming parser patch and three security backports are not
carried forward because v0.25.1 contains their replacements or upstream fixes.

The V2 runner contains native GPU-side metadata, async output, and MTP
implementations corresponding to most of the old CC stack. V2 is not enabled
for this release because stock v0.25.1 produced incorrect Gemma 4 output in
full-CC B300 tests, including eager no-MTP controls. The production candidate
therefore uses V1 while the remaining v0.23.0 performance patches are audited
and measured against the new baseline.

The custom uniform-decode metadata and dirty block-table kernels are also
excluded from the minimal candidate. They will only be ported if matched
full-CC measurements show a remaining regression that cannot be recovered by
the smaller patch set.

## Verification

Run:

```bash
validation/verify_patch_series.sh /path/to/vllm-checkout
```

The script checks out v0.25.1, applies all three patches with zero fuzz, and
diffs the result against the source branch commit above.
