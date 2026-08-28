# syntax=docker/dockerfile:1.6
#
# CC/MTP-optimized vLLM v0.28.0 V1 candidate. The amd64 base is digest-pinned so
# the full-CC comparison can be reproduced independently of mutable tags.
ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.28.0@sha256:61fc8a896b0a4fbbbdc063bc4b0dbc25ce98e02b5050c24aeb7830ac02039b14
FROM ${VLLM_BASE_IMAGE}

ARG SOURCE_REVISION=unversioned

COPY patches/ /tmp/tinfoil-patches/
RUN set -eux; \
    test -x /usr/bin/patch; \
    VLLM_PACKAGE_ROOT="$(python3 -c 'import pathlib, vllm; print(pathlib.Path(vllm.__file__).resolve().parent)')"; \
    VLLM_SITE_ROOT="$(dirname "$VLLM_PACKAGE_ROOT")"; \
    cd "$VLLM_SITE_ROOT"; \
    for p in /tmp/tinfoil-patches/*.patch; do \
        echo "Applying $(basename "$p")"; \
        /usr/bin/patch -p1 --no-backup-if-mismatch --fuzz=0 < "$p"; \
    done; \
    find "$VLLM_PACKAGE_ROOT" -name '__pycache__' -type d -exec rm -rf {} + || true; \
    rm -rf /tmp/tinfoil-patches; \
    python3 -c "import vllm; assert vllm.__version__.startswith('0.28.0'), vllm.__version__; print('vllm', vllm.__version__, 'with CC/MTP patches')"

# Gemma 4 video decoding reaches FFmpeg through OpenCV. The newest compatible
# OpenCV wheel does not yet contain FFmpeg 8.1.2, so video is disabled in the
# runtime config and the vulnerable codec surface is removed. Mooncake is not
# configured for this deployment and is removed with its build cache.
RUN set -eux; \
    for _ in 1 2 3; do \
        DISTS="$(python3 -c 'import importlib.metadata as md; m = md.packages_distributions(); print(" ".join(sorted(set((m.get("cv2") or []) + (m.get("mooncake") or [])))))')"; \
        [ -n "$DISTS" ] || break; \
        python3 -m pip uninstall -y $DISTS; \
    done; \
    rm -rf /opt/uv/cache; \
    python3 - <<'PY'
import importlib.util

for module in ("cv2", "mooncake"):
    spec = importlib.util.find_spec(module)
    assert spec is None, (
        f"{module} still importable: origin={spec.origin} "
        f"search={spec.submodule_search_locations}"
    )
PY

RUN python3 - <<'PY'
from pathlib import Path

import vllm

root = Path(vllm.__file__).resolve().parent
source = "\n".join(
    (root / relative).read_text()
    for relative in (
        "envs.py",
        "sampling_params.py",
        "platforms/cuda.py",
        "platforms/interface.py",
        "utils/platform_utils.py",
        "utils/torch_utils.py",
        "v1/worker/gpu_model_runner.py",
        "v1/worker/block_table.py",
        "v1/sample/rejection_sampler.py",
        "v1/spec_decode/llm_base_proposer.py",
    )
)
required = (
    "VLLM_CC_PAGEABLE_H2D",
    "prefer_pinned",
    "is_confidential_compute_enabled",
    "VLLM_DISABLE_STRUCTURED_OUTPUT_REGEX",
    "uses_grammar_constraint",
    "logitsprocs_need_output_token_ids=bool(custom_logitsprocs)",
    'share_embeddings and hasattr(self.model, "has_own_embed_tokens")',
    "VLLM_CC_OUTPUT_WORKER",
    "VLLM_CC_SPEC_COUNT_FAST_PUBLICATION",
    "VLLM_CC_DECODE_METADATA_FASTPATH",
    "VLLM_CC_BLOCK_TABLE_DIRTY_UPDATE",
    "self.pin_memory = PIN_MEMORY",
    "_cc_uniform_mtp_decode_metadata_kernel",
    "_coalesce_dirty_updates",
    "sampled_token_ids_np >= 0",
)
missing = [marker for marker in required if marker not in source]
if missing:
    raise SystemExit(f"missing v0.28.0 CC patch markers: {missing}")

# Import every patched module: a patch can apply cleanly yet reference a
# name the new base no longer imports, which only explodes at engine start.
import importlib

for module in (
    "vllm.v1.worker.gpu_model_runner",
    "vllm.v1.worker.gpu_worker",
    "vllm.v1.worker.block_table",
    "vllm.v1.core.sched.scheduler",
    "vllm.v1.engine.core",
    "vllm.v1.spec_decode.llm_base_proposer",
    "vllm.v1.spec_decode.extract_hidden_states",
    "vllm.v1.sample.rejection_sampler",
):
    importlib.import_module(module)

print("verified v0.28.0 V1 CC/MTP patch set")
PY

LABEL org.opencontainers.image.source="https://github.com/tinfoilsh/confidential-gemma4-31b" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      com.tinfoil.vllm.runtime-revision="f724246cc77483c6023b216e4fbd80b467df3c9f" \
      com.tinfoil.vllm.variant="cc-mtp-perf-v0.28.0-v1"
