#!/usr/bin/env python3
"""Behavior test for Gemma4 tool-argument parsing against the installed runtime.

Streams each tool call token-by-token through the installed ``Gemma4Parser``,
exactly as the frontend does, and checks that:

  1. the assembled arguments match the expected object,
  2. streaming and non-streaming extraction agree,
  3. a deeply nested tool call parses instead of raising RecursionError, and
  4. a structural-char-dense tool call streams a bounded number of argument
     chunks rather than one per structural token.

Checks 3 and 4 are the observable consequences of the two argument-parser
bounds. Both are driven entirely by the payload and read nothing from parser
internals, so this file also runs against an unpatched parser, where 3 raises
and 4 streams roughly one chunk per pair. Check 4 asserts on chunk counts
rather than elapsed time so that it stays deterministic on a loaded host.
"""

from __future__ import annotations

import argparse
import json
import time

from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
from vllm.parser.gemma4 import (
    STRING_DELIM,
    TOOL_CALL_END,
    TOOL_CALL_START,
    Gemma4Parser,
)

MODEL = "gemma4-31b"
DEFAULT_TOKENIZER = (
    "/tinfoil/mpk/"
    "mpk-cda2f261f72d80a847eb6fabea1f9949bf14ce5bb323808a8e2e4a9f09018357"
)

# CPython's default recursion limit is 1000 and the parser descends about one
# frame per level, so this sits well past where an unbounded parser dies.
NESTING_DEPTH = 1600

# Arguments that are almost entirely structural characters: the shape that
# forces a full re-parse on nearly every streamed token.
DENSE_PAIRS = 3200
# An unbounded parser emits roughly one argument chunk per pair. The bound
# asserted here is that the chunk count does not scale with payload size; the
# shipped parser converts once at tool-call end and so emits a single chunk.
MAX_ARG_CHUNKS = 800
# Backstop only, and deliberately loose: measured far below a second bounded
# and around twenty seconds unbounded.
MAX_DENSE_CPU_SECONDS = 5.0


def quoted(value: str) -> str:
    return f"{STRING_DELIM}{value}{STRING_DELIM}"


def model_output(raw_args: str) -> str:
    return f"{TOOL_CALL_START}call:do_work{{{raw_args}}}{TOOL_CALL_END}"


def nesting_args(depth: int) -> str:
    return "a:" + "{b:" * depth + "1" + "}" * depth


def dense_args(pairs: int) -> str:
    return ",".join(f"k{i}:{i % 10}" for i in range(pairs))


def build_cases() -> list[tuple[str, str, object]]:
    """Each case is (name, raw arguments, expected object)."""
    return [
        (
            "simple_string",
            f"location:{quoted('Tokyo')}",
            {"location": "Tokyo"},
        ),
        (
            "nested_object_and_array",
            f"location:{quoted('Tokyo')},"
            f"opts:{{unit:{quoted('celsius')},detail:{{level:3}}}},"
            f"tags:[{quoted('a')},{quoted('b')}]",
            {
                "location": "Tokyo",
                "opts": {"unit": "celsius", "detail": {"level": "3"}},
                "tags": ["a", "b"],
            },
        ),
        (
            # Bare scalars stay strings here: coercion to real JSON types is
            # applied later from the tool schema, and no tools are passed.
            "scalar_types",
            "enabled:true,disabled:false,missing:null,ratio:1.5",
            {
                "enabled": "true",
                "disabled": "false",
                "missing": "null",
                "ratio": "1.5",
            },
        ),
        (
            "delimiters_inside_string",
            f"note:{quoted('a, b: c, d')},other:{quoted('x')}",
            {"note": "a, b: c, d", "other": "x"},
        ),
        (
            "empty_args",
            "",
            {},
        ),
        (
            "long_string",
            f"body:{quoted(' '.join(['lorem'] * 700))}",
            {"body": " ".join(["lorem"] * 700)},
        ),
        (
            "long_array",
            "items:[" + ",".join(quoted(f"item-{i}") for i in range(300)) + "]",
            {"items": [f"item-{i}" for i in range(300)]},
        ),
        (
            "many_pairs",
            ",".join(f"key{i}:{quoted(f'value-{i}')}" for i in range(300)),
            {f"key{i}": f"value-{i}" for i in range(300)},
        ),
    ]


def stream_call(tokenizer, request, text: str) -> dict:
    """Feed one model output token-by-token, as the frontend does.

    Reports a RecursionError rather than propagating it, so the caller can
    fail with the nesting depth that caused it.
    """
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    pieces = [tokenizer.decode([i], skip_special_tokens=False) for i in token_ids]

    parser = Gemma4Parser(tokenizer)
    parser.initialize_streaming()

    arguments, names, chunks = "", [], 0

    def collect(delta) -> None:
        nonlocal arguments, chunks
        if delta is None:
            return
        for call in delta.tool_calls or []:
            if call.function is None:
                continue
            if call.function.name:
                names.append(call.function.name)
            if call.function.arguments:
                arguments += call.function.arguments
                chunks += 1

    started = time.process_time()
    try:
        for piece, token_id in zip(pieces, token_ids):
            collect(parser.parse_delta(piece, [token_id], request, finished=False))
        collect(parser.finish_streaming())
    except RecursionError:
        return {"recursion_error": True}

    return {
        "recursion_error": False,
        "arguments": arguments,
        "names": names,
        "tokens": len(token_ids),
        "chunks": chunks,
        "cpu": time.process_time() - started,
    }


def extract_call(tokenizer, request, text: str) -> tuple[str, list[str]]:
    """Parse the same output in one shot, as the non-streaming path does."""
    parser = Gemma4Parser(tokenizer)
    extracted = parser.extract_tool_calls(text, request)
    return (
        "".join(call.function.arguments or "" for call in extracted.tool_calls),
        [call.function.name for call in extracted.tool_calls],
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    args = ap.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    request = ChatCompletionRequest(
        messages=[{"role": "user", "content": "hi"}], model=MODEL
    )

    cases = build_cases()
    for name, raw_args, expected in cases:
        text = model_output(raw_args)

        streamed = stream_call(tokenizer, request, text)
        assert not streamed["recursion_error"], name
        assert streamed["names"] == ["do_work"], (name, streamed["names"])
        assert json.loads(streamed["arguments"]) == expected, (
            name,
            streamed["arguments"][:200],
        )

        extracted, extracted_names = extract_call(tokenizer, request, text)
        assert extracted_names == ["do_work"], (name, extracted_names)
        assert json.loads(extracted) == expected, (name, extracted[:200])

    # Deep nesting must parse rather than exhaust the interpreter stack. An
    # unbounded parser raises here, which surfaces as HTTP 500 in the frontend.
    nested = stream_call(tokenizer, request, model_output(nesting_args(NESTING_DEPTH)))
    assert not nested["recursion_error"], f"RecursionError at depth {NESTING_DEPTH}"
    assert nested["names"] == ["do_work"], nested["names"]
    assert isinstance(json.loads(nested["arguments"]), dict), nested["arguments"][:200]

    # Dense arguments must not provoke a re-parse per streamed token.
    dense = stream_call(tokenizer, request, model_output(dense_args(DENSE_PAIRS)))
    assert not dense["recursion_error"], "dense"
    assert json.loads(dense["arguments"]) == {
        f"k{i}": str(i % 10) for i in range(DENSE_PAIRS)
    }, dense["arguments"][:200]
    assert dense["chunks"] < MAX_ARG_CHUNKS, (dense["chunks"], dense["tokens"])
    assert dense["cpu"] < MAX_DENSE_CPU_SECONDS, dense["cpu"]

    print(
        json.dumps(
            {
                "cases": len(cases),
                "dense_chunks": dense["chunks"],
                "dense_cpu_seconds": round(dense["cpu"], 3),
                "dense_pairs": DENSE_PAIRS,
                "nesting_depth": NESTING_DEPTH,
                "status": "pass",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
