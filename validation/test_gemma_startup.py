"""Keep the deployed backend on Hopper and permit Blackwell auto-selection."""

import pytest

from serve import serving_command

BASE_COMMAND = ["/opt/tinfoil/inference-sidecar", "vllm", "serve"]
MODEL_ARGUMENTS = ["--model", "gpt-oss-120b", "--port", "8001"]
HOPPER_CAPABILITY_MAJOR = 9
BLACKWELL_CAPABILITY_MAJOR = 10


def test_hopper_keeps_flash_attention():
    assert serving_command(MODEL_ARGUMENTS, HOPPER_CAPABILITY_MAJOR) == [
        *BASE_COMMAND, *MODEL_ARGUMENTS, "--attention-backend", "FLASH_ATTN"
    ]


def test_blackwell_uses_vllm_backend_selection():
    assert serving_command(MODEL_ARGUMENTS, BLACKWELL_CAPABILITY_MAJOR) == [
        *BASE_COMMAND, *MODEL_ARGUMENTS
    ]


@pytest.mark.parametrize("capability_major", [HOPPER_CAPABILITY_MAJOR, BLACKWELL_CAPABILITY_MAJOR])
@pytest.mark.parametrize("backend", [["--attention-backend", "TRITON_ATTN"], ["--attention-backend=TRITON_ATTN"]])
def test_explicit_backend_is_preserved(capability_major, backend):
    arguments = [*MODEL_ARGUMENTS, *backend]
    assert serving_command(arguments, capability_major) == [*BASE_COMMAND, *arguments]
