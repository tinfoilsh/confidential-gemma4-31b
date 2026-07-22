# vLLM v0.23.0 CC/MTP Handoff

## Status

This branch packages the current Gemma 4 confidential-computing takeover
candidate for review and validation. It is not production-approved.

| Item | Value |
|---|---|
| vLLM base | `v0.23.0` / `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` |
| Candidate | `f49f4a1c5` |
| Preserved handoff | `52b60ccc7c48b5a36791036fbacd1bcc1911ca8f` |
| Source branch | `tinfoilsh/vllm-cc-opt:handoff/gemma4-cc-v0230-20260628` |
| Evidence | private `tinfoilsh/vllm-cc-gemma4-lab` repository |

The final matched throughput run measured 690.41 output tokens/second at
concurrency 8 under CC, versus 559.30 for stock CC and 713.99 for stock
non-CC. That recovered 84.8% of the stock CC throughput tax.

The headline run enabled block-table dirty updates. Later feature-isolation
work showed that the MTP decode metadata path passed seven of seven API cases
across three runs after commit `52b60ccc7`, but block-table dirty updates still
caused nondeterminism. Commit `f49f4a1c5` removes a concrete race by coalescing
overlapping dirty writes and sourcing them from the final CPU table. This
branch still disables that gate until the fix passes enclave validation.

## Required Before Release

1. Build the image and confirm all 15 patches apply with zero fuzz.
2. Run the seven API correctness cases three times with MTP enabled.
3. Run the same cases once without MTP.
4. Run a matched stock/candidate four-arm throughput sweep using the exact
   image that passed correctness.
5. Keep `VLLM_CC_BLOCK_TABLE_DIRTY_UPDATE=0` unless new committed evidence
   clears it.

Use `validation/validate_stock_candidate_cc.py` for API comparison. The lab
repository contains the original harness, result JSON, patch manifest, and the
remaining investigation plan.

## Local Verification Completed

- All 14 deployment patches apply to vLLM v0.23.0 with zero fuzz.
- Excluding the intentional structured-output patch, the resulting runtime
  package matches candidate `f49f4a1c5` file for file.
- Shell and Python validation tools pass syntax checks.
- `docker buildx build --check` resolves the pinned base and reports no
  Dockerfile warnings.

A full image build was not run on the curation host because the v0.23.0 image
was not cached and the filesystem had only 7.6GB free. The release workflow or
a build host with sufficient storage must perform the full build.
