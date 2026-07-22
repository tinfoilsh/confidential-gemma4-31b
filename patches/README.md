# vLLM v0.25.1 Deployment Patches

These 17 patches apply in filename order to the official vLLM v0.25.1
Python package. They were generated from
`tinfoilsh/vllm-cc-opt:milestone/gemma4-cc-v0251-v1-perf-b300-20260722` at
commit `56219cc43545d7959a3895752fba845727f2adee`.

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
- `0105`-`0111` remove avoidable V1 token-history and metadata copies and add
  a CC-gated asynchronous output publication path, including MTP acceptance
  counts.
- `0112`-`0116` add the uniform MTP metadata and dirty block-table kernels plus
  the stale-state and overlapping-update correctness repairs found during the
  original B300 validation.
- `0117` validates CC fast-path token domains and packed block-table metadata
  before it reaches the GPU kernels.

## Removed From v0.23.0

The v0.23.0 Gemma streaming parser patch and three security backports are not
carried forward because v0.25.1 contains their replacements or upstream fixes.

The V2 runner has native equivalents for much of this stack, but it is not
enabled: stock v0.25.1 produced incorrect Gemma 4 output in full-CC B300 tests,
including eager no-MTP controls. The candidate therefore uses V1 and preserves
the repaired V1 CC fast paths.

## Verification

Run:

```bash
validation/verify_patch_series.sh /path/to/vllm-checkout
```

The script checks out v0.25.1, applies all 17 patches with zero fuzz, and
diffs the result against the source branch commit above.
