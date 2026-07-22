# vLLM v0.23.0 CC/MTP Handoff

## Status

This branch packages the validated Gemma 4 confidential-computing production
candidate. Release `v0.0.21` has been published, measured, attested, and
revalidated from a clean full-CC enclave.

| Item | Value |
|---|---|
| vLLM base | `v0.23.0` / `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` |
| Candidate | `f49f4a1c5` |
| Preserved handoff | `52b60ccc7c48b5a36791036fbacd1bcc1911ca8f` |
| Source branch | `tinfoilsh/vllm-cc-opt:prod/gemma4-cc-v0230-b300-20260722` |
| Evidence | private `tinfoilsh/vllm-cc-gemma4-lab` repository |
| Validation host | inf14, NVIDIA B300, full CC enclave |
| Production release | `v0.0.21` |
| Production image | `sha256:a19c72bc11dd1a086e55c1e6af701e804e4f8dfeda134a7660105549309e8d9d` |

On the B300, stock v0.23.0 reached 569.05 output tokens/second at concurrency
8. The repaired five-gate candidate produced 891.10, 970.23, and 985.34
tokens/second in three identical runs, for a 970.23 median and a 70.5% gain
over stock. At concurrency 16, the candidate produced 993.09 and 972.14
tokens/second. Every benchmark completed with zero failed requests.

Sequential same-enclave restarts produced 956-1,015 tokens/second, but those
runs benefited from warm process/GPU state and are not used as the production
headline. Clean hardened releases produced 875.01 tokens/second without the
allocator override and 870.50 with it, which is indistinguishable at the
observed launch-to-launch variance. The production config conservatively
retains the long-standing `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
setting for allocator behavior, not as a claimed throughput optimization.

The exact `v0.0.21` release passed 70 sequential API requests and 140
concurrent oracle-checked requests in a fresh full-CC enclave. Its five c8 runs
ranged from 800.71 to 906.58 output tokens/second with an 870.50 median, 53.0%
above the matched stock v0.23.0 result of 569.05.

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

## Promotion Status

The technical promotion gates are complete. Roll out release `v0.0.21` using
the digest above and the tag-pinned `tinfoil-config.yml`. The private lab
repository contains the raw release, attestation, correctness, stress, and
benchmark evidence needed for review.

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
