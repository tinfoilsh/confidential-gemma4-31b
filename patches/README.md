# vLLM Deployment Patches

Patches apply in filename order to the installed vLLM package. They use
source-root paths (`a/vllm/...`) and are applied from the package's parent
directory with `patch -p1 --fuzz=0`.

## Patch Groups

- `0001-auto-enable-repetition-detection-structured-output.patch` is the
  existing Gemma 4 structured-output workaround, rebased onto v0.23.0.
- `0101` through `0113` are runtime-only exports of the preserved 13-commit
  handoff stack.
- `0114` coalesces overlapping dirty block-table writes before the Triton
  update kernel. It is the first takeover fix and still requires CC validation.

The current takeover candidate is commit `f49f4a1c5`, based on preserved
handoff commit `52b60ccc7c48b5a36791036fbacd1bcc1911ca8f` and vLLM v0.23.0 commit
`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`.

## Gate Status

The deployment configuration enables pageable H2D, output worker, count-only
fast publication, and decode metadata. It explicitly disables
`VLLM_CC_BLOCK_TABLE_DIRTY_UPDATE`; that gate remains on hold because the
latest local evidence shows nondeterministic correctness failures when enabled.

## Regenerating 0101-0114

From the preserved vLLM checkout:

```bash
git format-patch \
  --no-signature \
  --keep-subject \
  --start-number=101 \
  --output-directory /path/to/confidential-gemma4-31b/patches \
  v0.23.0..f49f4a1c5 -- vllm
```

The `-- vllm` path restriction intentionally excludes upstream tests from the
runtime image patch set. The complete patches, including tests, are preserved
in `vllm-cc-gemma4-lab`.

Run `validation/verify_patch_series.sh /path/to/vllm-checkout` after any patch
change. A Docker build must also pass before release.
