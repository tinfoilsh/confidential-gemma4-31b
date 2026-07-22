# confidential-gemma4-31b

Tinfoil confidential enclave configuration for
[`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

The active milestone branch ports the validated confidential-computing and MTP
optimization stack to vLLM v0.25.1. It is not a production release until the
full-CC validation recorded in [HANDOFF.md](HANDOFF.md) is complete.

## Repo layout

```
confidential-gemma4-31b/
├── Dockerfile                 builds on the digest-pinned vLLM v0.25.1 base
├── HANDOFF.md                 candidate status and required validation
├── patches/                   ordered deployment patch series
│   ├── 0101-0104-...          minimal CC, correctness, and upstream MTP fixes
│   ├── 0105-0117-...          V1 CC/MTP performance and safety fixes
│   └── README.md              provenance and regeneration instructions
├── validation/                API and source-level verification tools
├── tinfoil-config.yml         enclave configuration
└── .github/workflows/
    ├── tinfoil-build.yml      manual review/release image build
    └── tinfoil-release.yml    attestation and release publication
```

The authoritative implementation is
`tinfoilsh/vllm-cc-opt:milestone/gemma4-cc-v0251-v1-perf-b300-20260722`.
Experiment evidence is in the private `tinfoilsh/vllm-cc-gemma4-lab` repo.
