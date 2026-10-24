"""Check answer boundaries in the deployed Gemma chat template."""

import copy
import os
from pathlib import Path

import pytest
from jinja2.sandbox import ImmutableSandboxedEnvironment

TEMPLATE_PATH = Path(os.environ.get(
    "GEMMA_CHAT_TEMPLATE", "/vllm-workspace/examples/tool_chat_template_gemma4.jinja"
))
EMPTY_THOUGHT = "<|channel>thought\n<channel|>"
OPEN_THOUGHT = "<|channel>thought\n"
QUESTION = "Read the reference code."
TOOL_TEXT = '{"code":"R81462"}'
TOOL_CALL_ID = "call_document"
TOOL_NAME = "ReadDocument"


@pytest.fixture(scope="module")
def template():
    return ImmutableSandboxedEnvironment().from_string(TEMPLATE_PATH.read_text())


def conversation(image):
    content = TOOL_TEXT
    if image:
        content = [{"type": "text", "text": QUESTION}, {"type": "image_url"}]
    return [
        {"role": "user", "content": QUESTION},
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": TOOL_CALL_ID, "type": "function",
            "function": {"name": TOOL_NAME, "arguments": {}},
        }]},
        {"role": "tool", "tool_call_id": TOOL_CALL_ID, "content": content},
    ]


def render(template, messages, thinking, generation=True):
    return template.render(messages=messages, bos_token="<bos>",
                           enable_thinking=thinking, add_generation_prompt=generation)


@pytest.mark.parametrize("image", [False, True])
@pytest.mark.parametrize("thinking", [False, True])
def test_tool_result_has_explicit_answer_boundary(template, image, thinking):
    messages = conversation(image)
    history = render(template, messages, thinking, generation=False)
    prompt = render(template, messages, thinking)
    prefix = OPEN_THOUGHT if thinking else EMPTY_THOUGHT
    assert prompt == history + prefix
    assert history.endswith("<|image|>" if image else "<tool_response|>")
    if not image:
        assert TOOL_TEXT in prompt


@pytest.mark.parametrize("image", [False, True])
@pytest.mark.parametrize("thinking", [False, True])
def test_user_followup_starts_a_new_model_turn(template, image, thinking):
    messages = conversation(image)
    messages.append({"role": "user", "content": QUESTION})
    prompt = render(template, messages, thinking)
    suffix = "<|turn>model\n" + ("" if thinking else EMPTY_THOUGHT)
    assert prompt.endswith(suffix)
    tool_end = "<tool_response|>" + ("<|image|>" if image else "")
    assert tool_end + "<|turn>user\n" in prompt


@pytest.mark.parametrize("thinking", [False, True])
def test_parallel_results_get_one_final_answer_prefix(template, thinking):
    messages = conversation(image=True)
    second_call = copy.deepcopy(messages[1]["tool_calls"][0])
    second_call["id"] += "_second"
    messages[1]["tool_calls"].append(second_call)
    messages.append({"role": "tool", "tool_call_id": second_call["id"], "content": TOOL_TEXT})
    history = render(template, messages, thinking, generation=False)
    prompt = render(template, messages, thinking)
    assert history.count("<|tool_response>") == 2
    assert prompt == history + (OPEN_THOUGHT if thinking else EMPTY_THOUGHT)
    assert TOOL_TEXT in prompt


@pytest.mark.parametrize("thinking", [False, True])
def test_unanswered_tool_call_does_not_get_answer_prefix(template, thinking):
    prompt = render(template, conversation(image=False)[:-1], thinking)
    assert prompt.endswith("<tool_call|><|tool_response>")
