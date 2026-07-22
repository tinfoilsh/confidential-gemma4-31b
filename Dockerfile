# syntax=docker/dockerfile:1.6
#
# Stock vLLM v0.25.1 control. The amd64 base is digest-pinned so the full-CC
# comparison can be reproduced independently of mutable registry tags.
ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.25.1@sha256:f0b9a0dc75a9fca3b6811e3279367b2d6a448055a000bfd13859587d74cef268
FROM ${VLLM_BASE_IMAGE}

ARG SOURCE_REVISION=unversioned

# Security-only wheel updates are fetched by immutable PyPI artifact URL and
# verified by BuildKit before they enter the image.
ADD --checksum=sha256:78cb2c6865a35ab8ff8b75fd122f6033b92a62c82801110e48ddd6c936a45d91 \
    https://files.pythonhosted.org/packages/84/21/a35af28dcc61f37ed850a2d64c65c701321dfbf25085e469d5559360cbbf/pillow-12.3.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl \
    /tmp/security-wheels/pillow-12.3.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
ADD --checksum=sha256:2726bca5e7193f61c5dde8b12500a6de2d9acf6d1a1c0be9e8c2e706437991df \
    https://files.pythonhosted.org/packages/e2/5e/d118fce19f87a2e7d8101c35c8ae0ec289098a4df0ff244cec23e415aca0/mcp-1.28.1-py3-none-any.whl \
    /tmp/security-wheels/mcp-1.28.1-py3-none-any.whl
ADD --checksum=sha256:deda9277cfd454080ec40b207fb6df82206a3a2688735233cdcd8d3d565f088b \
    https://files.pythonhosted.org/packages/9a/3b/6163796d69c3977d1e4287bea4a6979161cbbdd170ebb430511e8e1999ce/pyasn1-0.6.4-py3-none-any.whl \
    /tmp/security-wheels/pyasn1-0.6.4-py3-none-any.whl

# Pin patched Ubuntu packages. Exact versions make the security delta
# reproducible and fail the build if the expected artifacts disappear.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        dirmngr=2.2.27-3ubuntu2.5 \
        gnupg=2.2.27-3ubuntu2.5 \
        gnupg-l10n=2.2.27-3ubuntu2.5 \
        gnupg-utils=2.2.27-3ubuntu2.5 \
        gnupg2=2.2.27-3ubuntu2.5 \
        gpg=2.2.27-3ubuntu2.5 \
        gpg-agent=2.2.27-3ubuntu2.5 \
        gpg-wks-client=2.2.27-3ubuntu2.5 \
        gpg-wks-server=2.2.27-3ubuntu2.5 \
        gpgconf=2.2.27-3ubuntu2.5 \
        gpgsm=2.2.27-3ubuntu2.5 \
        gpgv=2.2.27-3ubuntu2.5 \
        libssl3=3.0.2-0ubuntu1.25 \
        openssl=3.0.2-0ubuntu1.25; \
    rm -rf /var/lib/apt/lists/*

RUN python3 -c "import vllm; assert vllm.__version__.startswith('0.25.1'), vllm.__version__; print('stock vllm', vllm.__version__)"

# Gemma 4 video decoding reaches FFmpeg through OpenCV. The newest compatible
# OpenCV wheel does not yet contain FFmpeg 8.1.2, so video is disabled in the
# runtime config and the vulnerable codec surface is removed. Mooncake is not
# configured for this deployment and is removed with its build cache.
RUN set -eux; \
    python3 -m pip install --no-cache-dir --no-deps \
        /tmp/security-wheels/pillow-12.3.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl \
        /tmp/security-wheels/mcp-1.28.1-py3-none-any.whl \
        /tmp/security-wheels/pyasn1-0.6.4-py3-none-any.whl; \
    python3 -m pip uninstall -y opencv-python-headless mooncake-transfer-engine; \
    rm -rf /tmp/security-wheels /opt/uv/cache; \
    python3 - <<'PY'
import importlib.metadata
import importlib.util

expected = {
    "mcp": "1.28.1",
    "pillow": "12.3.0",
    "pyasn1": "0.6.4",
}
for distribution, version in expected.items():
    actual = importlib.metadata.version(distribution)
    assert actual == version, (distribution, actual, version)

assert importlib.util.find_spec("cv2") is None
assert importlib.util.find_spec("mooncake") is None
PY

LABEL org.opencontainers.image.source="https://github.com/tinfoilsh/confidential-gemma4-31b" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      com.tinfoil.vllm.runtime-revision="752a3a504485790a2e8491cacbb35c137339ad34" \
      com.tinfoil.vllm.variant="stock-v0.25.1-control"
