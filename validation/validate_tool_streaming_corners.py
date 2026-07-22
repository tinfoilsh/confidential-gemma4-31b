#!/usr/bin/env python3
"""Validate streamed tool-call framing and multi-turn corner cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from validate_stock_candidate_cc import (
    expected_base_payload,
    post_json,
    post_stream,
    strict_messages,
)


MODEL = "gemma4-31b"


def function_tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


LOOKUP_TOOL = function_tool(
    "lookup_order",
    "Look up an order by id.",
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"],
    },
)

WEATHER_TOOL = function_tool(
    "get_weather",
    "Get the current weather in one city.",
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)

TICKET_TOOL = function_tool(
    "submit_ticket",
    "Submit a deployment ticket.",
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "metadata": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "priority": {"type": "string", "enum": ["high"]},
                    "retry": {"type": "integer"},
                },
                "required": ["priority", "retry"],
            },
        },
        "required": ["title", "tags", "metadata"],
    },
)


def response_message(body: dict[str, Any]) -> dict[str, Any]:
    return (body.get("choices") or [{}])[0].get("message") or {}


def parsed_calls(body: dict[str, Any]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for call in response_message(body).get("tool_calls") or []:
        fn = call.get("function") or {}
        parsed.append(
            {
                "id": call.get("id"),
                "name": fn.get("name"),
                "arguments": json.loads(fn.get("arguments") or "{}"),
            }
        )
    return parsed


def stream_contract(body: dict[str, Any]) -> tuple[bool, str]:
    chunks = body.get("chunks") or []
    if not body.get("done") or not chunks:
        return False, "stream did not terminate with [DONE]"
    ids = {chunk.get("id") for chunk in chunks if chunk.get("id")}
    if len(ids) != 1:
        return False, f"stream changed completion id: {sorted(ids)!r}"
    objects = {chunk.get("object") for chunk in chunks}
    if objects != {"chat.completion.chunk"}:
        return False, f"unexpected stream objects: {sorted(objects)!r}"
    finish_reasons = [
        choice.get("finish_reason")
        for chunk in chunks
        for choice in chunk.get("choices", [])
        if choice.get("finish_reason")
    ]
    if not finish_reasons:
        return False, "stream omitted finish_reason"
    return True, "valid SSE framing, stable id, finish reason, and [DONE]"


def validate_one_call(
    body: dict[str, Any], name: str, arguments: dict[str, Any], *, stream: bool
) -> tuple[bool, str, Any]:
    try:
        calls = parsed_calls(body)
    except Exception as exc:
        return False, f"tool arguments are not valid JSON: {exc}", None
    if len(calls) != 1:
        return False, f"expected one tool call, got {len(calls)}", calls
    expected = {"name": name, "arguments": arguments}
    actual = {"name": calls[0]["name"], "arguments": calls[0]["arguments"]}
    if actual != expected or not calls[0]["id"]:
        return False, f"expected {expected!r} with an id, got {calls!r}", calls
    if stream:
        contract_ok, reason = stream_contract(body)
        if not contract_ok:
            return False, reason, calls
    return True, "tool call and arguments matched", calls


def validate_multi_call(body: dict[str, Any]) -> tuple[bool, str, Any]:
    try:
        calls = parsed_calls(body)
    except Exception as exc:
        return False, f"tool arguments are not valid JSON: {exc}", None
    actual = [(call["name"], call["arguments"]) for call in calls]
    expected = [
        ("get_weather", {"city": "Paris"}),
        ("get_weather", {"city": "Tokyo"}),
    ]
    contract_ok, contract_reason = stream_contract(body)
    ids = [call["id"] for call in calls]
    ok = actual == expected and all(ids) and len(set(ids)) == 2 and contract_ok
    return ok, (
        f"expected ordered calls {expected!r}; got {actual!r}; "
        f"stream={contract_reason}"
    ), calls


def validate_text(body: dict[str, Any], expected: str, *, stream: bool) -> tuple[bool, str, Any]:
    message = response_message(body)
    text = str(message.get("content") or "").strip()
    calls = message.get("tool_calls") or []
    contract_ok, contract_reason = (stream_contract(body) if stream else (True, "n/a"))
    ok = text == expected and not calls and contract_ok
    return ok, (
        f"expected text {expected!r} and no calls; got text={text!r}, "
        f"calls={calls!r}, stream={contract_reason}"
    ), {"text": text, "tool_calls": calls}


def build_cases() -> list[tuple[str, bool, dict[str, Any], Callable[[dict[str, Any]], tuple[bool, str, Any]]]]:
    cases: list[
        tuple[str, bool, dict[str, Any], Callable[[dict[str, Any]], tuple[bool, str, Any]]]
    ] = []

    payload = expected_base_payload(
        messages=strict_messages(
            'Call submit_ticket with title Deploy "CC" build, tags streaming and mtp, '
            "priority high, and retry 2. Do not answer in text."
        ),
        max_tokens=192,
        stream=True,
    )
    payload.update(
        {
            "tools": [TICKET_TOOL],
            "tool_choice": {
                "type": "function",
                "function": {"name": "submit_ticket"},
            },
            "stream_options": {"include_usage": True},
        }
    )
    ticket_args = {
        "title": 'Deploy "CC" build',
        "tags": ["streaming", "mtp"],
        "metadata": {"priority": "high", "retry": 2},
    }
    cases.append(
        (
            "stream_forced_nested_escaped_args",
            True,
            payload,
            lambda body: validate_one_call(
                body, "submit_ticket", ticket_args, stream=True
            ),
        )
    )

    payload = expected_base_payload(
        messages=strict_messages(
            "Use the appropriate tool to look up order ORDER-884. Do not answer in text."
        ),
        max_tokens=96,
        stream=True,
    )
    payload.update({"tools": [LOOKUP_TOOL, WEATHER_TOOL], "tool_choice": "auto"})
    cases.append(
        (
            "stream_auto_tool_selection",
            True,
            payload,
            lambda body: validate_one_call(
                body, "lookup_order", {"order_id": "ORDER-884"}, stream=True
            ),
        )
    )

    payload = expected_base_payload(
        messages=strict_messages(
            "Do not call a tool. Reply with exactly NO_TOOL_REQUIRED."
        ),
        max_tokens=24,
        stream=True,
    )
    payload.update({"tools": [LOOKUP_TOOL, WEATHER_TOOL], "tool_choice": "auto"})
    cases.append(
        (
            "stream_auto_no_tool_fallback",
            True,
            payload,
            lambda body: validate_text(body, "NO_TOOL_REQUIRED", stream=True),
        )
    )

    payload = expected_base_payload(
        messages=strict_messages(
            "Call get_weather once for Paris and once for Tokyo, in that order. "
            "Make exactly two tool calls and do not answer in text."
        ),
        max_tokens=192,
        stream=True,
    )
    payload.update(
        {
            "tools": [WEATHER_TOOL],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
    )
    cases.append(("stream_parallel_tool_calls", True, payload, validate_multi_call))

    continuation_messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": "Follow the user's response format exactly.",
        },
        {"role": "user", "content": "Look up order ORDER-731."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_lookup_731",
                    "type": "function",
                    "function": {
                        "name": "lookup_order",
                        "arguments": '{"order_id":"ORDER-731"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_lookup_731",
            "content": '{"status":"shipped","eta":"Friday"}',
        },
        {
            "role": "user",
            "content": "Using the tool result, reply with exactly SHIPPED_FRIDAY.",
        },
    ]
    payload = expected_base_payload(
        messages=continuation_messages, max_tokens=24, stream=True
    )
    payload.update({"tools": [LOOKUP_TOOL], "tool_choice": "none"})
    cases.append(
        (
            "stream_tool_result_continuation",
            True,
            payload,
            lambda body: validate_text(body, "SHIPPED_FRIDAY", stream=True),
        )
    )

    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")

    results: dict[str, Any] = {
        "schema": "vllm_cc_tool_streaming_corners.v1",
        "url": args.url,
        "requested_runs": args.runs,
        "cases": {},
    }
    failures: list[str] = []
    for name, stream, payload, validator in build_cases():
        case_runs: list[dict[str, Any]] = []
        for run_number in range(1, args.runs + 1):
            print(f"running {name} ({run_number}/{args.runs})", flush=True)
            raw = (
                post_stream(args.url, payload, timeout=args.timeout)
                if stream
                else post_json(args.url, payload, timeout=args.timeout)
            )
            if not raw.get("ok"):
                run = {
                    "run_number": run_number,
                    "passed": False,
                    "status": raw.get("status"),
                    "reason": "API or stream failure",
                    "raw": raw.get("body"),
                }
            else:
                passed, reason, normalized = validator(raw["body"])
                run = {
                    "run_number": run_number,
                    "passed": passed,
                    "status": raw.get("status"),
                    "reason": reason,
                    "normalized": normalized,
                    "raw": raw["body"],
                }
            case_runs.append(run)
        passed = all(run["passed"] for run in case_runs)
        results["cases"][name] = {"passed": passed, "runs": case_runs}
        if not passed:
            failures.append(name)

    results["summary"] = {
        "total_cases": len(results["cases"]),
        "total_requests": len(results["cases"]) * args.runs,
        "failed_cases": failures,
        "passed": not failures,
    }
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(results["summary"], indent=2, sort_keys=True), flush=True)
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
