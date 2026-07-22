# syntax=docker/dockerfile:1.6
#
# Patched vLLM image. Base is digest-pinned for attestation. See HANDOFF.md
# and patches/README.md for the candidate's evidence and patch provenance.
ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.23.0@sha256:6d8429e38e3747723ca07ee1b17972e09bb9c51c4032b266f24fb1cc3b22ed8f
FROM ${VLLM_BASE_IMAGE}

# Patches use vLLM source-root paths (a/vllm/...). Discover the installed
# package instead of assuming a Python minor-version-specific location.
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
    python3 -c "import vllm; assert vllm.__version__.startswith('0.23.0'), vllm.__version__; print('vllm', vllm.__version__, 'with tinfoil patches')"

RUN python3 - <<'PY'
import inspect

import vllm
from vllm.v1.worker import gpu_model_runner

source = inspect.getsource(gpu_model_runner)
required = (
    "VLLM_CC_OUTPUT_WORKER",
    "VLLM_CC_SPEC_COUNT_FAST_PUBLICATION",
    "VLLM_CC_DECODE_METADATA_FASTPATH",
    "_cc_uniform_mtp_decode_metadata_kernel",
    "_cc_mtp_decode_gpu_synced",
)
missing = [marker for marker in required if marker not in source]
if missing:
    raise SystemExit(f"missing CC/MTP patch markers: {missing}")

print("verified vLLM", vllm.__version__, "CC/MTP handoff patches")
PY
