# Validation

`verify_patch_series.sh` applies the deployment patches to exact vLLM v0.31.0
and verifies the selected runtime's source hashes. The Docker build runs the
existing UVA fallback and Gemma request-policy CPU tests; CUDA cases are skipped
when no GPU is available.

`test_gemma_template.py` checks tool-result answer boundaries, thinking modes,
and user follow-ups. Set `GEMMA_CHAT_TEMPLATE` to a patched template path when
running it outside the container; the Docker build tests the deployed template.

`test_gemma_mm_prefix.py` checks that large image-attention ranges survive on
models that clamp them inside the kernel, while preserving the size limit for
other models. It runs in the Docker build with the patched runtime.

Endpoint validation, stress tests, and benchmark tooling are maintained separately
from this deployment repository. Keep correctness results outside this repository.
