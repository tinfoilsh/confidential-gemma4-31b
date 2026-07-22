# vLLM v0.23.0 CC/MTP Handoff

## Status

This branch packages the validated Gemma 4 confidential-computing production
candidate. Release-image publication and a clean-enclave rerun remain before
deployment promotion.

| Item | Value |
|---|---|
| vLLM base | `v0.23.0` / `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` |
| Candidate | `f49f4a1c5` |
| Preserved handoff | `52b60ccc7c48b5a36791036fbacd1bcc1911ca8f` |
| Source branch | `tinfoilsh/vllm-cc-opt:prod/gemma4-cc-v0230-b300-20260722` |
| Evidence | private `tinfoilsh/vllm-cc-gemma4-lab` repository |
| Validation host | inf14, NVIDIA B300, full CC enclave |
| Candidate image ID | `sha256:04637d3bc136eeff0f5b56685b7640a900c7e27a57242b9d031b661e3a162b95` |

On the B300, stock v0.23.0 reached 569.05 output tokens/second at concurrency
8. The repaired five-gate candidate produced 891.10, 970.23, and 985.34
tokens/second in three identical runs, for a 970.23 median and a 70.5% gain
over stock. At concurrency 16, the candidate produced 993.09 and 972.14
tokens/second. Every benchmark completed with zero failed requests.

The old `52b60ccc7` image passed 21 sequential requests with dirty updates
disabled, then failed all seven API cases and became nondeterministic across 70
requests when only that gate was enabled. Commit `f49f4a1c5` coalesces
overlapping writes and sources each merged range from the authoritative final
CPU block table. With the gate enabled, the fixed image passed:

- 5,000 randomized coalescing property cases;
- 70 of 70 sequential requests across seven API modes;
- 140 of 140 shuffled requests at concurrency 16 with zero oracle mismatches;
- 70 of 70 no-MTP requests; and
- nine matched MTP load-sweep runs with zero request failures.

## Required Before Release

1. Publish the v0.0.19 release image from this exact branch.
2. Launch a fresh full-CC enclave from the published digest.
3. Repeat the deterministic API suite and a matched c8 benchmark.
4. Record the attested digest and clean-enclave evidence in the lab repository.

Use `validation/validate_stock_candidate_cc.py` for API comparison. The lab
repository contains the original harness, result JSON, patch manifest, and the
remaining investigation plan.

## Verification Completed

- All 15 deployment patches apply to vLLM v0.23.0 with zero fuzz.
- Excluding the intentional structured-output patch, the resulting runtime
  package matches candidate `f49f4a1c5` file for file.
- Shell and Python validation tools pass syntax checks.
- `docker buildx build --check` resolves the pinned base and reports no
  Dockerfile warnings.
- The full candidate image built inside a writable full-CC enclave and passed
  the correctness, stress, regression, and benchmark suites above.
