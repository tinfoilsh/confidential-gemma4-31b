# vLLM v0.25.1 Deployment Patches

These patches apply in filename order to the official vLLM v0.25.1
Python package. `0101`-`0119` were generated from
`tinfoilsh/vllm-cc-opt:milestone/gemma4-cc-v0251-v1-perf-b300-20260722`.
`0120`-`0121` continue that series on
`tinfoilsh/vllm-cc-opt:security/gemma4-tool-parser-dos-20260728`, branched
from its tip. The whole series is exported from commit
`2c8af33d916a7e26255b130b513bdc7cc99ffe92`.

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
- `0118` registers the deployment gates with vLLM's environment validator;
  this removes misleading unknown-variable warnings without changing behavior.
- `0119` initializes the v0.25.1 runner's host-staging policy for the ported
  output and metadata paths. It fixes the missing `pin_memory` attribute found
  by the first full-CC endpoint request.
- `0120` bounds the Gemma4 tool-argument parser's nesting depth. The
  recursive-descent parser re-sliced the buffer at each level, so a deeply
  nested tool-call argument caused quadratic CPU growth and, past the Python
  recursion limit, a RecursionError surfacing as HTTP 500 that stalled the
  frontend event loop -- a remotely triggerable DoS via crafted model output.
  Capping at depth 64 (far above any real tool call) truncates deeper
  structure with a warning instead of crashing. Reproduced and verified on
  the shipped v0.0.23 image; upstream fixed the analogous issue only in the
  (experimental, unusable-with-our-config) Rust frontend.
- `0121` stops the Gemma4 parser re-parsing the whole argument buffer on every
  streamed structural token, which made a large tool call cost O(N^2): a 3,200
  pair call burned 22 s of frontend CPU. Arguments are now converted once when
  the tool call ends, so cost is linear and the assembled arguments are
  byte-identical. Tool names still stream immediately; only the argument blob
  arrives in a single delta, and nothing downstream can act on partial
  arguments anyway.

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

The script checks out v0.25.1, applies all 21 patches with zero fuzz, and
diffs the result against the source branch commit above.
