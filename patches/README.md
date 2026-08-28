# vLLM v0.28.0 Deployment Patches

These 17 patches apply in filename order to the official vLLM v0.28.0
Python package. They were generated from
`tinfoilsh/vllm-cc-opt:milestone/gemma4-cc-v0280-v1-20260827` at
commit `4138b301d488dbb2fdbe379bc38aeaeab57c987c` (the v0.25.1 series
rebased onto v0.28.0).

## Included

- `0101` allows this public deployment to reject user-provided regex
  constraints. The upstream compilation timeout remains in place.
- `0102` centralizes the pageable-host-staging policy at the global
  `PIN_MEMORY` hook. `VLLM_CC_PAGEABLE_H2D=1` avoids pinned staging in full CC.
- `0103` enables vLLM's repetition detector for grammar-constrained Gemma
  output while preserving an explicit all-zero caller opt-out.
- `0106`-`0111` remove avoidable V1 token-history and metadata copies and add
  a CC-gated asynchronous output publication path, including MTP acceptance
  counts.
- `0112`-`0116` add the uniform MTP metadata and dirty block-table kernels plus
  the stale-state and overlapping-update correctness repairs found during the
  original B300 validation.
- `0117` validates CC fast-path token domains and packed block-table metadata
  before it reaches the GPU kernels.
- `0118` registers the deployment gates with vLLM's environment validator;
  this removes misleading unknown-variable warnings without changing behavior.
- `0119` initializes the runner's host-staging policy for the ported
  output and metadata paths. It fixes the missing `pin_memory` attribute found
  by the first full-CC endpoint request.

## Retired at v0.28.0

- `0104` (Gemma 4 MTP embedding sharing, upstream `b2b8f679d`) is in the
  v0.28.0 tag, with additional upstream hardening (`272abd5f48`).
- `0105` (avoid reasoning-parser token history copies): v0.28.0 ships the
  same `logitsprocs_need_output_token_ids` narrowing natively, with dynamic
  thinking-budget tracking that supersedes this patch's static form.

Numbering is stable across rebases: retired numbers are never reused.

## Removed From v0.23.0

The v0.23.0 Gemma streaming parser patch and three security backports are not
carried forward because v0.25.1 contains their replacements or upstream fixes.

The V2 runner has native equivalents for much of this stack, but it is not
enabled: stock v0.25.1 produced incorrect Gemma 4 output in full-CC B300 tests,
so the deployment forces the V1 runner (`VLLM_USE_V2_MODEL_RUNNER=0`), which
remains fully supported at v0.28.0.

## Verification

Run:

```bash
validation/verify_patch_series.sh /path/to/vllm-checkout
```

The script checks out v0.28.0, applies all 17 patches with zero fuzz, and
diffs the result against the source branch commit above.
