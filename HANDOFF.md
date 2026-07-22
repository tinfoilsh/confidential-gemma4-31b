# vLLM v0.23.0 CC/MTP Handoff

## Status

This branch packages the security-hardened successor to the validated Gemma 4
confidential-computing performance candidate. Release `v0.0.21` remains a
prerelease and must not be promoted: its exact image predates the security
backports and dependency hardening described below.

| Item | Value |
|---|---|
| vLLM base | `v0.23.0` / `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` |
| Hardened candidate | `21edb0a1e` |
| Preserved handoff | `52b60ccc7c48b5a36791036fbacd1bcc1911ca8f` |
| Source branch | `tinfoilsh/vllm-cc-opt:prod/gemma4-cc-v0230-b300-20260722` |
| Evidence | private `tinfoilsh/vllm-cc-gemma4-lab` repository |
| Validation host | inf14, NVIDIA B300, full CC enclave |
| Prior prerelease | `v0.0.21` |
| Prior image | `sha256:a19c72bc11dd1a086e55c1e6af701e804e4f8dfeda134a7660105549309e8d9d` |
| Security review | in progress; promotion blocked pending fresh CC validation |

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

Promotion is blocked until the hardened candidate is rebuilt, rescanned,
attested, and rerun through the clean full-CC correctness, concurrency, no-MTP,
and performance gates. Do not deploy `v0.0.21`.

Security hardening after the original performance validation includes:

- official vLLM backports for three high-severity advisories;
- rejection of public structured-output regex constraints, in addition to the
  upstream compilation timeout;
- bounds checks before the CC dirty block-table Triton write;
- strict release source/tag validation and least-privilege workflow defaults;
- patched OpenSSL, GnuPG, Pillow, MCP, and pyasn1 packages;
- removal of the unused Mooncake connector; and
- explicit video disablement plus OpenCV removal until its wheel carries
  FFmpeg 8.1.2 or newer. Image input remains enabled.

Use `validation/validate_stock_candidate_cc.py` for API comparison. The lab
repository contains the original harness, result JSON, patch manifest, and the
remaining investigation plan.

## Verification Completed

- The prior 15-patch image applied to vLLM v0.23.0 with zero fuzz.
- The hardened 20-patch series applies with zero fuzz and matches candidate
  `21edb0a1e` plus the intentional structured-output patch; runtime and full-CC
  verification are pending.
- Shell and Python validation tools pass syntax checks.
- `docker buildx build --check` resolves the pinned base and reports no
  Dockerfile warnings.
- The prior candidate image built inside a writable full-CC enclave and passed
  the correctness, stress, regression, and benchmark suites above.
