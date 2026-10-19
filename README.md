# confidential-gemma4-31b

Tinfoil confidential enclave configuration for
[`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

The vLLM v0.31.0 candidate uses MRV2, FlashAttention, and four MTP proposals
with probabilistic drafting. Its scheduler keeps an 8192-token batch budget
and a 2048-token prefill threshold to limit interference with decoding.

- [tinfoil-config.yml](tinfoil-config.yml): model, runtime, and enclave settings.
- [Dockerfile](Dockerfile): digest-pinned build with the inference sidecar.
- [patches/README.md](patches/README.md): runtime patches and source verification.
- [validation/README.md](validation/README.md): existing validation tools.
