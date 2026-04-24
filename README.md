# confidential-gemma4-31b

Tinfoil confidential enclave configuration for
[`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

This repo ships its own patched vLLM image rather than using the upstream
`vllm/vllm-openai` directly. The patches address two bugs that caused
sustained production stalls on gemma4-31b:

1. Head-of-line blocking in the scheduler's waiter-admission loop when the
   head waiter fails the `can_fit_full_sequence` check — upstream
   [vllm-project/vllm#39734](https://github.com/vllm-project/vllm/issues/39734).
2. Sliding-window attention admission math over-budgeting by 2–3× for
   hybrid SWA + full-attention models (gemma, mistral-sliding, phi-3/4) —
   upstream [vllm-project/vllm#39866](https://github.com/vllm-project/vllm/pull/39866).

Background on the investigation:
[`tinfoilsh/experiments-fix-gemma`](https://github.com/tinfoilsh/experiments-fix-gemma).

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

## Build / release flow (dual-workflow, same as confidential-websearch)

```bash
# Trigger a new release:
gh workflow run tinfoil-build.yml -f version=v0.0.6
```

Order of operations inside `tinfoil-build.yml`:

1. Check `v0.0.6` tag doesn't already exist
2. Docker build this repo's `Dockerfile` → produces a reproducible image
3. Push to `ghcr.io/tinfoilsh/confidential-gemma4-31b:v0.0.6@sha256:…`
4. `tinfoilsh/update-container-action` updates `image:` in
   `tinfoil-config.yml` to the new pinned digest and creates the `v0.0.6` tag
5. Triggers `tinfoil-release.yml` which runs `tinfoilsh/measure-image-action`
   to produce the attested release

## Updating the vLLM base image

Bump `VLLM_BASE_IMAGE` in the `Dockerfile` to the new digest-pinned ref,
then rebuild. If any patch fails to apply, see
[`patches/README.md`](patches/README.md) for the refresh / drop procedure.

## Current vLLM config rationale

See [`patches/README.md`](patches/README.md) for per-patch details. The
config in `tinfoil-config.yml`:

- `--scheduling-policy priority` — lets the model router
  (`tinfoilsh/confidential-model-router`) inject priority per request, so
  short/latency-sensitive requests can be served ahead of long-context
  ones even when the engine is busy. With patches 2+3 the admission math
  is now correct, so we don't need the `--max-model-len` cap anymore.
- No `--max-model-len` override — the model's native 262,144-token max is
  used. Patches 2+3 ensure this is safe under load.
- No `--async-scheduling` — disabled during the 2026-04-22 incident and
  kept off until the patched image has baked in prod for a while.
