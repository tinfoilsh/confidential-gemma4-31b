# confidential-gemma4-31b

Tinfoil confidential enclave configuration for
[`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

This branch ports the confidential-computing and MTP optimization stack to
vLLM v0.28.0 (rebased from the B300-validated v0.25.1 series; full-CC
re-validation of this base is in progress). [HANDOFF.md](HANDOFF.md) records
the v0.25.1 candidate's immutable identities, results, and release procedure.

## Repo layout

```
confidential-gemma4-31b/
├── Dockerfile                 builds on the digest-pinned vLLM v0.28.0 base
├── HANDOFF.md                 candidate status and required validation
├── patches/                   ordered deployment patch series
│   ├── 0101-0103-...          minimal CC and correctness fixes
│   ├── 0106-0119-...          V1 CC/MTP performance and safety fixes
│   └── README.md              provenance and regeneration instructions
├── validation/                API and source-level verification tools
├── tinfoil-config.yml         enclave configuration
└── .github/workflows/
    ├── tinfoil-release.yml    review image and release build
    └── tinfoil-release-publish.yml
                               release measurement and publication
```

The authoritative implementation is
`tinfoilsh/vllm-cc-opt:milestone/gemma4-cc-v0280-v1-20260827`.
Experiment evidence is in the private `tinfoilsh/vllm-cc-gemma4-lab` repo.
