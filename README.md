# confidential-gemma4-31b

Tinfoil confidential enclave configuration for
[`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

## Repo layout

```
confidential-gemma4-31b/
├── Dockerfile                 builds on the pinned vllm/vllm-openai base
├── patches/                   unified-diff patches applied at build time
│   ├── 0001-sched-waiter-loop-hol-fix.patch
│   ├── 0002-swa-admission-budget-cap.patch
│   ├── 0003-swa-allocate-new-blocks-cap.patch
│   └── README.md              how to add / update patches
├── tinfoil-config.yml         enclave configuration
└── .github/workflows/
    ├── tinfoil-build.yml      manual workflow_dispatch: build → push → bump config → tag
    └── tinfoil-release.yml    measure-image-action + publish
```
