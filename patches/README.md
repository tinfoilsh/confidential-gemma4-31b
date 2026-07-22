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
  update kernel. It is the first takeover fix and has passed full-CC validation
  on an NVIDIA B300.
- `0115` validates dirty-update bounds and rejects malformed negative sampled
  token IDs.
- `0116` through `0118` backport the official fixes for
  `GHSA-8wr5-jm2h-8r4f`, `GHSA-rwxx-mrjm-wc2m`, and
  `GHSA-33cg-gxv8-3p8g` from vLLM 0.24.0.
- `0119` lets public deployments reject user-provided regex constraints
  entirely, in addition to the upstream compilation timeout.

The hardened takeover candidate is commit `21edb0a1e`, based on preserved
handoff commit `52b60ccc7c48b5a36791036fbacd1bcc1911ca8f` and vLLM v0.23.0 commit
`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`.

## Gate Status

The deployment configuration enables all five gates, including
`VLLM_CC_BLOCK_TABLE_DIRTY_UPDATE`. The preserved handoff image failed all
seven API cases across 70 requests with that gate enabled. Candidate
`f49f4a1c5` passed the same 70-request sequence, a 140-request concurrent
oracle comparison, and a 70-request no-MTP control. Raw evidence is in the
private `tinfoilsh/vllm-cc-gemma4-lab` repository.

The security additions require a new image and full-CC regression run. The
functional results below apply to `f49f4a1c5`; they are the comparison baseline,
not a security sign-off for `21edb0a1e`.

## Regenerating 0101-0119

From the preserved vLLM checkout:

```bash
git format-patch \
  --no-signature \
  --keep-subject \
  --start-number=101 \
  --output-directory /path/to/confidential-gemma4-31b/patches \
  v0.23.0..21edb0a1e -- vllm
```

The `-- vllm` path restriction intentionally excludes upstream tests from the
runtime image patch set. The complete patches, including tests, are preserved
in `vllm-cc-gemma4-lab`.

Run `validation/verify_patch_series.sh /path/to/vllm-checkout` after any patch
change. A Docker build must also pass before release.
