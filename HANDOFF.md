# vLLM v0.25.1 Gemma 4 CC/MTP Handoff

## Status

Ready for review, merge, and a release build from `main`. Do not promote the
commit-addressed review image directly; after merge, dispatch the release
workflow so it builds, pins, measures, attests, and publishes the final image.

| Item | Immutable value |
|---|---|
| vLLM base | `v0.25.1` / `752a3a504485790a2e8491cacbb35c137339ad34` |
| vLLM candidate | `tinfoilsh/vllm-cc-opt@f7ccdd0596cb6899bc0b32a1ca581d9f67250db7` |
| vLLM branch | `milestone/gemma4-cc-v0251-v1-perf-b300-20260722` |
| Deployment candidate | `b4426497a6c06df09bf96b1f87a886c574764abe` |
| Review image | `sha256:fc473096b8527c19bf44e7d164772a70e61c225d0a6d936a7d8f5be204f08372` |
| AMD64 manifest | `sha256:698ea028d6b63474364d8e340837ed868142bc39fb6c50877273051e377f2a45` |
| Review build | GitHub Actions run `29958352779` |
| Validation | INF14, one NVIDIA B300, full CPU and GPU CC |
| Evidence | private `tinfoilsh/vllm-cc-gemma4-lab` repository |

## Model Identity

- Target: `google/gemma-4-31B-it@842da3794eaa0b77d5f08bae87a17459d91ff475`
- Target MPK: `cda2f261f72d80a847eb6fabea1f9949bf14ce5bb323808a8e2e4a9f09018357_62578692096_827ad0bf-94a4-5620-9569-8f3a34cc5154`
- Assistant: `google/gemma-4-31B-it-assistant@34ef9f029d1c52bccac2def222523af32f3ccd0f`
- Assistant MPK: `2d92158d05e976de143bd05ff87977c73523ce6adeff1b559ebf32a2d230d634_971251712_27ee073f-136c-5855-a1a3-1fdc293ec0bb`

The target tensor files are byte-identical to the preceding HF revision. The
new MPK intentionally carries the updated tokenizer, chat template, and model
metadata.

## Runtime Decision

Use vLLM V1 with `TRITON_ATTN` and MTP=4. These are correctness constraints:

- Stock v0.25.1 V2 produced corrupted Gemma output with MTP, without MTP,
  with automatic or explicit Triton attention, and under eager execution.
- Stock v0.25.1 V1 produced correct output without MTP.
- Stock v0.25.1 V1 MTP failed initialization because the release predates
  upstream fix `b2b8f679d` / PR #47953. Patch `0104` carries that fix.
- FlashInfer MTP graph capture selected a TRT-LLM kernel unavailable for
  Gemma 4's 512-wide draft attention. Explicit Triton is the supported path.

These controls rule out MTP, CUDA graphs, the modelpack, and CC alone as the
cause of V2 corruption. Do not enable V2 for this release.

## Correctness

The exact review image passed in a full-CC enclave:

| Suite | Result |
|---|---:|
| Deterministic text, streaming, JSON/schema, named tools | 35/35 |
| Streaming tool corner cases | 25/25 |
| Responses API text, tools, continuation, parallel tools, image | 30/30 |
| Concurrent oracle-checked stress, concurrency 16 | 140/140 |
| Randomized dirty block-table schedules | 5,000/5,000 |
| Throughput requests across five runs | 320/320 |

There were no output mismatches, nondeterministic cases, failed benchmark
requests, or token-count discrepancies. Inline image inference returned the
correct result; streaming, auto and forced tool calls, escaped/nested tool
arguments, parallel calls, and tool-result continuation all passed.

Runtime policy checks confirmed that regex constraints, remote-media SSRF,
local-file media, video, and negative prompt token IDs are blocked. Sixty-four
cancelled streams at concurrency 16 left the engine healthy. One inherited
v0.25.1 response-semantics issue remains: a blocked `file://` image returns
HTTP 500 instead of 4xx. No file is read and the engine remains healthy.

## Performance

Headline contract: 64 random prompts, 1,024 input tokens, 256 output tokens,
concurrency 8, infinite request rate, seed 20260722, temperature 0, ignore EOS,
MTP=4, and `max-num-seqs=8`.

| Full-CC arm | Five-run output tok/s | Median |
|---|---|---:|
| Minimal v0.25.1 V1 MTP repair | 675.77, 668.66, 677.74, 696.48, 695.41 | 677.74 |
| Full v0.25.1 V1 CC/MTP port | 906.34, 968.29, 965.95, 972.70, 976.72 | **968.29** |

The full port is 42.9% faster than the minimal MTP repair. Its median MTP
acceptance was 58.20%; all five runs processed exactly 65,536 input and 16,384
output tokens. A stock v0.25.1 V1 no-MTP reference reached 415.11 tok/s, but it
is not a matched MTP comparison and its benchmark client inherited the model's
sampling default instead of explicitly setting temperature 0.

The result is within 0.2% of the prior optimized v0.23.0 headline median of
970.23 tok/s. Correctness plus performance parity means non-CC differential
tracing is not required before shipment.

## Patch Scope

The 19 runtime-only patches are documented in `patches/README.md`. The port
keeps the five CC performance techniques, carries the post-v0.25.1 Gemma MTP
fix, and removes obsolete v0.23.0 patches:

- three security backports already present in v0.25.1;
- the old Gemma streaming-parser patch, replaced by v0.25.1's parser engine;
- benchmark-only MTP observability from the production runtime.

`validation/verify_patch_series.sh` applies every patch to exact v0.25.1 with
zero fuzz and diffs the result against `f7ccdd0596cb6899bc0b32a1ca581d9f67250db7`.

## Release Procedure

1. Merge this branch to `main`.
2. Dispatch `tinfoil-release.yml` on `main` with the next strict SemVer and
   `review_only=false`.
3. Confirm the workflow creates a release-only child commit that changes only
   `tinfoil-config.yml`, pins the built digest, and tags that child.
4. Confirm the publish workflow measures, attests, and publishes the release.

No test containers or images remain on INF14, and production was not modified.
