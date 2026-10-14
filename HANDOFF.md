# vLLM v0.31.0 candidate

This package reproduces the selected H200 full-CC runtime sources and scheduling
settings. It preserves the deployment's inference sidecar, forced usage reporting,
model revisions, authenticated endpoints, and media restrictions.

The configuration uses one GPU, 16 vCPUs, 128 GiB guest RAM, a 64 GiB serving
limit, and 16 GiB shared memory. MRV2, explicit UVA fallback, and the first-layer
RMS policy are enabled; the five V1 optimization gates are retired. Verify
MRV2 and FlashAttention version 4 in startup logs on the target H200.

The source hashes bind the packaged patches to the selected runtime. A release
build has its own image identity; the complete deployment wrapper still needs
canary verification. Existing model-answer limitations remain. This change does
not qualify other GPU models or non-CC operation.

After review and merge, the existing release workflow builds, pins, measures,
attests, and publishes the image. The zero image digest in the source config is
replaced by that workflow. No release or production rollout is part of this PR.
