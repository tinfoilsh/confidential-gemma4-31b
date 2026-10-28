"""Preserve GPU defaults and explicit serving overrides."""

import json

import pytest

from serve import serving_command

BASE_COMMAND = ["/opt/tinfoil/inference-sidecar", "vllm", "serve"]
MODEL_ARGUMENTS = ["--model", "gpt-oss-120b", "--port", "8001"]
HOPPER_CAPABILITY = (9, 0)
B200_CAPABILITY = (10, 0)
B300_CAPABILITY = (10, 3)
MTP_CONFIG = {"method": "mtp", "model": "gpt-oss-120b"}


def test_hopper_keeps_flash_attention():
    assert serving_command(MODEL_ARGUMENTS, HOPPER_CAPABILITY) == [
        *BASE_COMMAND, *MODEL_ARGUMENTS, "--attention-backend", "FLASH_ATTN"
    ]


def test_b200_uses_vllm_backend_selection():
    assert serving_command(MODEL_ARGUMENTS, B200_CAPABILITY) == [
        *BASE_COMMAND, *MODEL_ARGUMENTS
    ]


def test_b300_uses_triton_attention():
    assert serving_command(MODEL_ARGUMENTS, B300_CAPABILITY) == [
        *BASE_COMMAND, *MODEL_ARGUMENTS, "--attention-backend", "TRITON_ATTN"
    ]


@pytest.mark.parametrize("capability", [HOPPER_CAPABILITY, B200_CAPABILITY, B300_CAPABILITY])
@pytest.mark.parametrize("backend", [["--attention-backend", "FLASHINFER"], ["--attention-backend=TRITON_ATTN"], ["--attention_backend", "FLASHINFER"]])
def test_explicit_backend_is_preserved(capability, backend):
    arguments = [*MODEL_ARGUMENTS, *backend]
    assert serving_command(arguments, capability) == [*BASE_COMMAND, *arguments]


@pytest.mark.parametrize("capability,count,backend", [
    (HOPPER_CAPABILITY, "4", ["--attention-backend", "FLASH_ATTN"]),
    (B200_CAPABILITY, "4", []),
    (B300_CAPABILITY, "6", ["--attention-backend", "TRITON_ATTN"]),
])
def test_mtp_budget_defaults_for_each_gpu(capability, count, backend):
    arguments = [*MODEL_ARGUMENTS, "--speculative-config", json.dumps(MTP_CONFIG)]
    assert serving_command(arguments, capability) == [
        *BASE_COMMAND, *arguments, *backend, "--spec-tokens", count
    ]


@pytest.mark.parametrize("flag", ["--speculative-config", "--speculative-config=", "--speculative_config", "-sc"])
@pytest.mark.parametrize("key", ["num_speculative_tokens", "num-speculative-tokens"])
def test_explicit_json_proposal_count_is_preserved(flag, key):
    config = json.dumps({**MTP_CONFIG, key: 2})
    option = [flag + config] if flag.endswith("=") else [flag, config]
    arguments = [*MODEL_ARGUMENTS, *option]
    assert serving_command(arguments, B300_CAPABILITY) == [
        *BASE_COMMAND, *arguments, "--attention-backend", "TRITON_ATTN"
    ]


@pytest.mark.parametrize("option", [["--spec-tokens", "2"], ["--spec-tokens=2"], ["--spec_tokens", "2"]])
def test_explicit_scalar_proposal_count_is_preserved(option):
    arguments = [*MODEL_ARGUMENTS, "--speculative-config", json.dumps(MTP_CONFIG), *option]
    assert serving_command(arguments, B300_CAPABILITY) == [
        *BASE_COMMAND, *arguments, "--attention-backend", "TRITON_ATTN"
    ]


def test_other_speculation_methods_keep_their_defaults():
    arguments = [*MODEL_ARGUMENTS, "--speculative-config", '{"method":"ngram"}']
    assert serving_command(arguments, B300_CAPABILITY) == [
        *BASE_COMMAND, *arguments, "--attention-backend", "TRITON_ATTN"
    ]


def test_dotted_speculation_options_are_passed_through():
    arguments = [*MODEL_ARGUMENTS, "--speculative-config", json.dumps(MTP_CONFIG),
                 "--speculative-config.num_speculative_tokens=2"]
    assert serving_command(arguments, B300_CAPABILITY) == [
        *BASE_COMMAND, *arguments, "--attention-backend", "TRITON_ATTN"
    ]
