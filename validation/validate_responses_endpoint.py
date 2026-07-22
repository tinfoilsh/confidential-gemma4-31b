#!/usr/bin/env python3
"""Validate Responses API streaming, tools, continuation, and images."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

from validate_security_endpoint import png_data_url


MODEL = "gemma4-31b"


def function_tool(name: str, description: str, argument: str) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {argument: {"type": "string"}},
            "required": [argument],
        },
        "strict": True,
    }


LOOKUP_TOOL = function_tool("lookup_order", "Look up an order by id.", "order_id")
WEATHER_TOOL = function_tool("get_weather", "Get weather for one city.", "city")
TIME_TOOL = function_tool("get_time", "Get local time for one city.", "city")


def event_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json", exclude_none=True)
    return {"type": getattr(event, "type", type(event).__name__)}


def streamed_function_calls(stream: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    completed: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    saw_response_completed = False
    for event in stream:
        events.append(event_dict(event))
        if event.type == "response.output_item.done" and event.item.type == "function_call":
            completed.append(
                {
                    "call_id": event.item.call_id,
                    "name": event.item.name,
                    "arguments": json.loads(event.item.arguments),
                }
            )
        elif event.type == "response.completed":
            saw_response_completed = True
    if not saw_response_completed:
        raise AssertionError("stream omitted response.completed")
    return completed, events


def streamed_text(stream: Any) -> tuple[str, list[dict[str, Any]]]:
    parts: list[str] = []
    events: list[dict[str, Any]] = []
    saw_completed = False
    for event in stream:
        events.append(event_dict(event))
        if event.type == "response.output_text.delta":
            parts.append(event.delta)
        elif event.type == "response.completed":
            saw_completed = True
    if not saw_completed:
        raise AssertionError("stream omitted response.completed")
    return "".join(parts).strip(), events


def run_once(client: OpenAI) -> dict[str, Any]:
    cases: dict[str, Any] = {}

    text, events = streamed_text(
        client.responses.create(
            model=MODEL,
            input="Reply with exactly RESPONSES_STREAM_OK.",
            stream=True,
            temperature=0,
            max_output_tokens=32,
        )
    )
    cases["stream_text"] = {
        "passed": text == "RESPONSES_STREAM_OK",
        "text": text,
        "events": events,
    }

    calls, events = streamed_function_calls(
        client.responses.create(
            model=MODEL,
            input="Call lookup_order for ORDER-991. Do not answer in text.",
            tools=[LOOKUP_TOOL],
            tool_choice={"type": "function", "name": "lookup_order"},
            stream=True,
            temperature=0,
            max_output_tokens=96,
        )
    )
    cases["stream_forced_tool"] = {
        "passed": len(calls) == 1
        and calls[0]["name"] == "lookup_order"
        and calls[0]["arguments"] == {"order_id": "ORDER-991"},
        "calls": calls,
        "events": events,
    }

    calls, events = streamed_function_calls(
        client.responses.create(
            model=MODEL,
            input=(
                "Use tools only. Call get_weather for Berlin and get_time for "
                "Tokyo, in that order."
            ),
            tools=[WEATHER_TOOL, TIME_TOOL],
            tool_choice="auto",
            parallel_tool_calls=True,
            stream=True,
            temperature=0,
            max_output_tokens=192,
        )
    )
    expected_calls = [
        {"name": "get_weather", "arguments": {"city": "Berlin"}},
        {"name": "get_time", "arguments": {"city": "Tokyo"}},
    ]
    actual_calls = [
        {"name": call["name"], "arguments": call["arguments"]} for call in calls
    ]
    cases["stream_parallel_tools"] = {
        "passed": actual_calls == expected_calls
        and len({call["call_id"] for call in calls}) == 2,
        "calls": calls,
        "events": events,
    }

    first = client.responses.create(
        model=MODEL,
        input="Call lookup_order for ORDER-731. Do not answer in text.",
        tools=[LOOKUP_TOOL],
        tool_choice={"type": "function", "name": "lookup_order"},
        temperature=0,
        max_output_tokens=96,
    )
    call = next(item for item in first.output if item.type == "function_call")
    continued_input = [
        {"role": "user", "content": "Call lookup_order for ORDER-731."},
        call.model_dump(mode="json", exclude_none=True),
        {
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": '{"status":"shipped","eta":"Friday"}',
        },
        {
            "role": "user",
            "content": "Reply with exactly RESPONSES_CONTINUATION_OK.",
        },
    ]
    continuation = client.responses.create(
        model=MODEL,
        input=continued_input,
        temperature=0,
        max_output_tokens=32,
    )
    cases["tool_result_continuation"] = {
        "passed": continuation.output_text.strip() == "RESPONSES_CONTINUATION_OK",
        "text": continuation.output_text.strip(),
        "response": continuation.model_dump(mode="json", exclude_none=True),
    }

    image_text, events = streamed_text(
        client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "What is the dominant color in this image? "
                                "Reply with one uppercase color word."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": png_data_url(),
                            "detail": "auto",
                        },
                    ],
                }
            ],
            stream=True,
            temperature=0,
            max_output_tokens=16,
        )
    )
    cases["stream_image"] = {
        "passed": "red" in image_text.lower(),
        "text": image_text,
        "events": events,
    }

    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")

    client = OpenAI(base_url=f"{args.url.rstrip('/')}/v1", api_key="unused")
    runs: list[dict[str, Any]] = []
    failed: list[str] = []
    for run_number in range(1, args.runs + 1):
        print(f"running Responses API matrix ({run_number}/{args.runs})", flush=True)
        cases = run_once(client)
        runs.append({"run_number": run_number, "cases": cases})
        failed.extend(
            f"run-{run_number}:{name}"
            for name, result in cases.items()
            if not result["passed"]
        )

    result = {
        "schema": "vllm_cc_responses_endpoint.v1",
        "url": args.url,
        "runs": runs,
        "summary": {
            "runs": args.runs,
            "cases_per_run": 5,
            "total_requests": args.runs * 6,
            "failed_cases": failed,
            "passed": not failed,
        },
    }
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["summary"], indent=2, sort_keys=True), flush=True)
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
