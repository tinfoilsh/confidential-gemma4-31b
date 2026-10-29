# syntax=docker/dockerfile:1.6
#
# The amd64 base preserves the compiled extensions used by the selected runtime.
ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.31.0@sha256:a4a4c0437bf7240089da5f08aa370c4aee17ae5290f7a3b468825ee26c4c3a6b
ARG SIDECAR_IMAGE=ghcr.io/tinfoilsh/inference-sidecar@sha256:65ce23d6560c46a1e8614ede187fcbf9798b267aa33878905b4872404787f47d
FROM ${SIDECAR_IMAGE} AS sidecar

FROM ${VLLM_BASE_IMAGE}

ARG SOURCE_REVISION=unversioned

ENV VLLM_USE_V2_MODEL_RUNNER=1 \
    VLLM_DISABLE_UVA=1 \
    VLLM_DISABLE_STRUCTURED_OUTPUT_REGEX=1

COPY patches/ /tmp/tinfoil-patches/
RUN set -eux; \
    test "$VLLM_BUILD_COMMIT" = db9527a46873454610df6dbedf79a36d6bf1a7f6; \
    cd /tmp/tinfoil-patches; \
    sha256sum --check series.sha256; \
    VLLM_PACKAGE_ROOT="$(python3 -c 'import importlib.util; print(next(iter(importlib.util.find_spec("vllm").submodule_search_locations)))')"; \
    cd "$(dirname "$VLLM_PACKAGE_ROOT")"; \
    sha256sum --check /tmp/tinfoil-patches/upstream.sha256; \
    for patch_file in /tmp/tinfoil-patches/*.patch; do \
        patch --batch --forward -p1 --no-backup-if-mismatch --fuzz=0 < "$patch_file"; \
    done; \
    sha256sum --check /tmp/tinfoil-patches/runtime.sha256; \
    cd /vllm-workspace; \
    sha256sum --check /tmp/tinfoil-patches/templates/upstream.sha256; \
    patch --batch --forward -p1 --no-backup-if-mismatch --fuzz=0 < /tmp/tinfoil-patches/templates/0005-gemma-tool-answer-prefix.patch; \
    sha256sum --check /tmp/tinfoil-patches/templates/runtime.sha256; \
    find "$VLLM_PACKAGE_ROOT" -name '__pycache__' -type d -exec rm -rf {} +; \
    rm -rf /tmp/tinfoil-patches

# Video is disabled in the serving configuration; remove its optional codec path.
RUN uv pip uninstall --offline --system --python /usr/bin/python3.12 \
      opencv-python-headless mooncake-transfer-engine mooncake-transfer-engine-cuda13 && \
    rm -rf /opt/uv/cache && \
    python3 - <<'PY'
import importlib.util

assert importlib.util.find_spec("cv2") is None
assert importlib.util.find_spec("mooncake") is None
PY

COPY serve.py /opt/tinfoil/serve.py
COPY validation/test-requirements.txt validation/test_gemma_policy.py validation/test_uva.py validation/test_gemma_template.py validation/test_gemma_mm_prefix.py validation/test_gemma_startup.py validation/test_gemma_blackwell_routing.py /opt/tinfoil-tests/
RUN uv venv --system-site-packages --python /usr/bin/python3.12 /opt/tinfoil-tests/.venv && \
    env -u UV_OVERRIDE uv pip install --python /opt/tinfoil-tests/.venv/bin/python --require-hashes \
      -r /opt/tinfoil-tests/test-requirements.txt && \
    PYTHONPATH=/opt/tinfoil /opt/tinfoil-tests/.venv/bin/python -m pytest --noconftest -q \
      /opt/tinfoil-tests/test_gemma_policy.py /opt/tinfoil-tests/test_uva.py /opt/tinfoil-tests/test_gemma_template.py /opt/tinfoil-tests/test_gemma_mm_prefix.py /opt/tinfoil-tests/test_gemma_startup.py /opt/tinfoil-tests/test_gemma_blackwell_routing.py && \
    rm -rf /opt/tinfoil-tests /opt/uv/cache

COPY --from=sidecar /inference-sidecar /opt/tinfoil/inference-sidecar
ENTRYPOINT ["python3", "/opt/tinfoil/serve.py"]

LABEL org.opencontainers.image.source="https://github.com/tinfoilsh/confidential-gemma4-31b" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      com.tinfoil.vllm.runtime-revision="db9527a46873454610df6dbedf79a36d6bf1a7f6" \
      com.tinfoil.vllm.variant="cc-mrv2-mtp-v0.31.0"
