"""Exercise the released Gemma request policies on the upgraded runtime."""

from types import SimpleNamespace

import pytest

from vllm.config import StructuredOutputsConfig
from vllm.exceptions import VLLMValidationError
from vllm.sampling_params import (
    RepetitionDetectionParams,
    SamplingParams,
    StructuredOutputsParams,
)

REGEX_ENVIRONMENT_KEY = "VLLM_DISABLE_STRUCTURED_OUTPUT_REGEX"
GEMMA_REPETITION_DEFAULT = (20, 3, 4)
DISABLED_REPETITION = (0, 0, 0)
EXPLICIT_REPETITION = (16, 2, 8)
TEST_MAX_TOKENS = 32
JSON_SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}}
GRAMMAR = 'root ::= "ok"'


def guard_values(guard):
    if guard is None:
        return None
    return (guard.max_pattern_size, guard.min_pattern_size, guard.min_count)


@pytest.mark.parametrize(
    "constraint",
    [{"json": JSON_SCHEMA}, {"json_object": True}, {"grammar": GRAMMAR}],
)
def test_grammar_requests_receive_the_released_guard(constraint):
    params = SamplingParams(structured_outputs=StructuredOutputsParams(**constraint))
    assert guard_values(params.repetition_detection) == GEMMA_REPETITION_DEFAULT


@pytest.mark.parametrize(
    "constraint",
    [None, {"choice": ["yes", "no"]}, {"regex": "a+"}, {"structural_tag": "{}"}],
)
def test_other_requests_do_not_receive_a_repetition_default(constraint):
    structured = None if constraint is None else StructuredOutputsParams(**constraint)
    assert SamplingParams(structured_outputs=structured).repetition_detection is None


@pytest.mark.parametrize("values", [DISABLED_REPETITION, EXPLICIT_REPETITION])
def test_explicit_guard_takes_precedence_on_grammar_requests(values):
    guard = RepetitionDetectionParams(
        max_pattern_size=values[0], min_pattern_size=values[1], min_count=values[2]
    )
    params = SamplingParams(
        structured_outputs=StructuredOutputsParams(json_object=True),
        repetition_detection=guard,
    )
    assert guard_values(params.repetition_detection) == values


def test_request_guard_mutation_does_not_affect_the_next_request():
    first = SamplingParams(structured_outputs=StructuredOutputsParams(json_object=True))
    first.repetition_detection.min_count = TEST_MAX_TOKENS
    second = SamplingParams(
        structured_outputs=StructuredOutputsParams(json_object=True)
    )
    assert guard_values(second.repetition_detection) == GEMMA_REPETITION_DEFAULT
    assert first.repetition_detection is not second.repetition_detection


@pytest.mark.parametrize("explicit_disable", [False, True])
def test_chat_json_conversion_preserves_default_and_opt_out(explicit_disable):
    from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest

    body = {
        "model": "gpt-oss-120b",
        "messages": [{"role": "user", "content": "Return a JSON object."}],
        "response_format": {"type": "json_object"},
    }
    if explicit_disable:
        body["repetition_detection"] = dict(
            zip(
                ("max_pattern_size", "min_pattern_size", "min_count"),
                DISABLED_REPETITION,
            )
        )
    params = ChatCompletionRequest.model_validate(body).to_sampling_params(
        max_tokens=TEST_MAX_TOKENS, default_sampling_params={}
    )
    expected = DISABLED_REPETITION if explicit_disable else GEMMA_REPETITION_DEFAULT
    assert guard_values(params.repetition_detection) == expected


@pytest.mark.parametrize("pattern", ["a+", "", " \n", "(a+)+", "\x00"])
def test_regex_policy_rejects_before_backend_selection(monkeypatch, pattern):
    monkeypatch.setenv(REGEX_ENVIRONMENT_KEY, "1")
    params = SamplingParams(structured_outputs=StructuredOutputsParams(regex=pattern))
    with pytest.raises(VLLMValidationError, match="regex is disabled by the server"):
        params._validate_structured_outputs(
            SimpleNamespace(is_diffusion=False), StructuredOutputsConfig(), object()
        )
    assert params.structured_outputs._backend is None


@pytest.mark.parametrize("raw", [None, "0"])
def test_disabled_regex_policy_preserves_upstream_validation(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv(REGEX_ENVIRONMENT_KEY, raising=False)
    else:
        monkeypatch.setenv(REGEX_ENVIRONMENT_KEY, raw)
    params = SamplingParams(structured_outputs=StructuredOutputsParams(regex="a\x00"))
    with pytest.raises(VLLMValidationError, match="must not contain a NUL character"):
        params._validate_structured_outputs(
            SimpleNamespace(is_diffusion=False), StructuredOutputsConfig(), object()
        )


@pytest.mark.parametrize(
    "constraint",
    [{"json": JSON_SCHEMA}, {"json_object": True}, {"choice": ["yes", "no"]}],
)
def test_regex_policy_preserves_other_valid_constraints(monkeypatch, constraint):
    pytest.importorskip("xgrammar")
    monkeypatch.setenv(REGEX_ENVIRONMENT_KEY, "1")
    params = SamplingParams(structured_outputs=StructuredOutputsParams(**constraint))
    params._validate_structured_outputs(
        SimpleNamespace(is_diffusion=False),
        StructuredOutputsConfig(backend="xgrammar"),
        object(),
    )
    assert params.structured_outputs._backend == "xgrammar"
