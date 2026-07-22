# vLLM v0.25.1 Deployment Patches

These three patches apply in filename order to the official vLLM v0.25.1
Python package. They were generated from
`tinfoilsh/vllm-cc-opt:milestone/gemma4-cc-v0251-b300-20260722` at commit
`7fee659f95cb868adf8eb47bd82f98710f98475f`.

## Included

- `0101` allows this public deployment to reject user-provided regex
  constraints. The upstream compilation timeout remains in place.
- `0102` centralizes the pageable-host-staging policy at v0.25.1's global
  `PIN_MEMORY` hook. `VLLM_CC_PAGEABLE_H2D=1` avoids pinned staging in full CC.
- `0103` enables vLLM's repetition detector for grammar-constrained Gemma
  output while preserving an explicit all-zero caller opt-out.

## Removed From v0.23.0

The v0.23.0 output-publication worker, accepted-count publication, token-history
plumbing, MTP stale-count fixes, Gemma streaming parser patch, and three
security backports are not carried forward. v0.25.1 contains native async
output/MTP implementations, the corresponding correctness fixes, a replacement
Gemma parser, and the upstream security fixes.

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
