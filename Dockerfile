# syntax=docker/dockerfile:1.6
#
# Patched vLLM image. Base is digest-pinned for attestation. See patches/
# for the diff set and README.md for the patching playbook.
ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.20.0-cu130@sha256:328268a8e0ceb9fccd301cca6599654908c3cac0e328ddce953c933b432924ef
FROM ${VLLM_BASE_IMAGE}

# Patches are -p1 unified diffs rooted at /; they target
# usr/local/lib/python3.12/dist-packages/... to match the base image.
COPY patches/ /tmp/tinfoil-patches/
RUN set -eux; \
    test -x /usr/bin/patch; \
    cd /; \
    for p in /tmp/tinfoil-patches/*.patch; do \
        echo "Applying $(basename "$p")"; \
        /usr/bin/patch -p1 --no-backup-if-mismatch --fuzz=0 < "$p"; \
    done; \
    find /usr/local/lib/python3.12/dist-packages/vllm -name '__pycache__' -type d -exec rm -rf {} + || true; \
    rm -rf /tmp/tinfoil-patches; \
    python3 -c "import vllm; print('vllm', vllm.__version__, 'with tinfoil patches')"
