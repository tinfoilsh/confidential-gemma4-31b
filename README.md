# confidential-gemma4-31b

Tinfoil confidential enclave configuration for
[`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

The active security-review branch integrates the preserved vLLM v0.23.0
confidential-computing and MTP optimization stack plus current security
backports. It is not a production release. Read [HANDOFF.md](HANDOFF.md) before
building or enabling additional feature gates.

## Repo layout

```
confidential-gemma4-31b/
├── Dockerfile                 builds on the pinned vLLM v0.23.0 base
├── HANDOFF.md                 candidate status and required validation
├── patches/                   ordered deployment patch series
│   ├── 0001-...               Gemma structured-output workaround
│   ├── 0101-0119-...          vLLM CC/MTP and security backports
│   └── README.md              provenance and regeneration instructions
├── validation/                API and source-level verification tools
├── tinfoil-config.yml         enclave configuration
└── .github/workflows/
    ├── tinfoil-build.yml      manual workflow_dispatch: build → push → bump config → tag
    └── tinfoil-release.yml    measure-image-action + publish
```

The authoritative implementation is the head of pull request 16 in
`tinfoilsh/vllm-cc-opt`. Experiment and security-review evidence is in the
private `tinfoilsh/vllm-cc-gemma4-lab` repository.
