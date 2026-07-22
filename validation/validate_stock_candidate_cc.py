#!/usr/bin/env python3
"""Compare stock and candidate vLLM API behavior under the same CC enclave.

This intentionally tests user-visible OpenAI-compatible behavior rather than
internal counters: non-streaming text, streaming text, JSON/schema output, and
tool-call formatting.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MODEL = "gemma4-31b"


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    value = value.strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        if len(lines) >= 2:
            value = "\n".join(lines[1:-1]).strip()
    return value


def post_json(
    base_url: str,
    payload: dict[str, Any],
    *,
    timeout: int,
) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": resp.status, "body": json.loads(body)}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except Exception:
            parsed = body
        return {"ok": False, "status": exc.code, "body": parsed}


def post_stream(
    base_url: str,
    payload: dict[str, Any],
    *,
    timeout: int,
) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "accept": "text/event-stream",
        },
        method="POST",
    )
    chunks: list[dict[str, Any]] = []
    done = False
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    done = True
                    break
                chunks.append(json.loads(data))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except Exception:
            parsed = body
        return {"ok": False, "status": exc.code, "body": parsed}

    content_parts: list[str] = []
    finish_reasons: list[str] = []
    tool_calls: dict[int, dict[str, Any]] = {}
    for chunk in chunks:
        for choice in chunk.get("choices", []):
            reason = choice.get("finish_reason")
            if reason:
                finish_reasons.append(reason)
            delta = choice.get("delta") or {}
            if delta.get("content"):
                content_parts.append(delta["content"])
            for tc in delta.get("tool_calls") or []:
                idx = int(tc.get("index", 0))
                dst = tool_calls.setdefault(
                    idx,
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                if tc.get("id"):
                    dst["id"] += tc["id"]
                if tc.get("type"):
                    dst["type"] = tc["type"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    dst["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    dst["function"]["arguments"] += fn["arguments"]
    body = {
        "object": "chat.completion.stream.assembled",
        "chunks": chunks,
        "done": done,
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "".join(content_parts),
                    "tool_calls": [tool_calls[i] for i in sorted(tool_calls)],
                },
                "finish_reason": finish_reasons[-1] if finish_reasons else None,
            }
        ],
    }
    return {"ok": done, "status": 200, "body": body}


def message(resp: dict[str, Any]) -> dict[str, Any]:
    return (resp.get("choices") or [{}])[0].get("message") or {}


def text_content(resp: dict[str, Any]) -> str:
    return normalize_text(message(resp).get("content"))


def tool_calls(resp: dict[str, Any]) -> list[dict[str, Any]]:
    return message(resp).get("tool_calls") or []


def parse_json_text(text: str) -> Any:
    text = normalize_text(text)
    return json.loads(text)


def expected_base_payload(
    *,
    messages: list[dict[str, Any]],
    max_tokens: int = 64,
    stream: bool = False,
) -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "top_p": 1.0,
        "seed": 20260626,
        "max_tokens": max_tokens,
        "stream": stream,
        "reasoning_effort": "none",
        "include_reasoning": False,
    }


def strict_messages(user: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a strict API conformance test model. Follow the user's "
                "format exactly. Do not include markdown or explanations."
            ),
        },
        {"role": "user", "content": user},
    ]


def validation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["ok"]},
            "count": {"type": "integer", "enum": [3]},
            "items": {
                "type": "array",
                "prefixItems": [
                    {"type": "string", "enum": ["red"]},
                    {"type": "string", "enum": ["blue"]},
                ],
                "minItems": 2,
                "maxItems": 2,
            },
        },
        "required": ["status", "count", "items"],
    }


def expected_json_obj() -> dict[str, Any]:
    return {"status": "ok", "count": 3, "items": ["red", "blue"]}


def tool_spec() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "description": "Look up an order by id.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The external order id.",
                        }
                    },
                    "required": ["order_id"],
                },
            },
        }
    ]


@dataclass(frozen=True)
class Case:
    name: str
    payload: dict[str, Any]
    stream: bool
    validator: Any


def validate_exact(expected: str):
    def inner(resp: dict[str, Any]) -> tuple[bool, str, Any]:
        actual = text_content(resp)
        ok = actual == expected
        return ok, f"expected exact {expected!r}, got {actual!r}", actual

    return inner


def validate_json_expected(resp: dict[str, Any]) -> tuple[bool, str, Any]:
    actual_text = text_content(resp)
    try:
        actual = parse_json_text(actual_text)
    except Exception as exc:
        return False, f"JSON parse failed: {exc}; text={actual_text!r}", actual_text
    ok = actual == expected_json_obj()
    return ok, f"expected JSON {expected_json_obj()!r}, got {actual!r}", actual


def validate_tool_expected(resp: dict[str, Any]) -> tuple[bool, str, Any]:
    calls = tool_calls(resp)
    if len(calls) != 1:
        return False, f"expected exactly one tool call, got {len(calls)}", calls
    call = calls[0]
    fn = call.get("function") or {}
    name = fn.get("name")
    raw_args = fn.get("arguments") or ""
    try:
        args = json.loads(raw_args)
    except Exception as exc:
        return False, f"tool args JSON parse failed: {exc}; args={raw_args!r}", call
    ok = name == "lookup_order" and args == {"order_id": "ORDER-731"}
    return ok, f"expected lookup_order ORDER-731, got name={name!r} args={args!r}", {
        "name": name,
        "arguments": args,
    }


def build_cases() -> list[Case]:
    cases: list[Case] = []

    payload = expected_base_payload(
        messages=strict_messages("Return exactly this token and nothing else: CC_VALIDATION_OK"),
        max_tokens=16,
    )
    cases.append(Case("exact_text_nonstream", payload, False, validate_exact("CC_VALIDATION_OK")))

    payload = expected_base_payload(
        messages=strict_messages("Return exactly this token and nothing else: STREAM_VALIDATION_OK"),
        max_tokens=16,
        stream=True,
    )
    cases.append(Case("exact_text_stream", payload, True, validate_exact("STREAM_VALIDATION_OK")))

    json_messages = strict_messages(
        "Return exactly this JSON object with no markdown: "
        '{"status":"ok","count":3,"items":["red","blue"]}'
    )
    payload = expected_base_payload(messages=json_messages, max_tokens=96)
    payload["response_format"] = {"type": "json_object"}
    cases.append(Case("json_object_nonstream", payload, False, validate_json_expected))

    payload = expected_base_payload(messages=json_messages, max_tokens=96)
    payload["response_format"] = {
        "type": "json_schema",
        "json_schema": {
            "name": "ValidationPayload",
            "schema": validation_schema(),
            "strict": True,
        },
    }
    cases.append(Case("json_schema_nonstream", payload, False, validate_json_expected))

    payload = expected_base_payload(messages=json_messages, max_tokens=96, stream=True)
    payload["response_format"] = {
        "type": "json_schema",
        "json_schema": {
            "name": "ValidationPayload",
            "schema": validation_schema(),
            "strict": True,
        },
    }
    cases.append(Case("json_schema_stream", payload, True, validate_json_expected))

    tool_payload = expected_base_payload(
        messages=strict_messages(
            "Call the lookup_order tool with order_id ORDER-731. Do not answer in text."
        ),
        max_tokens=96,
    )
    tool_payload["tools"] = tool_spec()
    tool_payload["tool_choice"] = {
        "type": "function",
        "function": {"name": "lookup_order"},
    }
    cases.append(Case("tool_call_named_nonstream", tool_payload, False, validate_tool_expected))

    tool_payload = expected_base_payload(
        messages=strict_messages(
            "Call the lookup_order tool with order_id ORDER-731. Do not answer in text."
        ),
        max_tokens=96,
        stream=True,
    )
    tool_payload["tools"] = tool_spec()
    tool_payload["tool_choice"] = {
        "type": "function",
        "function": {"name": "lookup_order"},
    }
    cases.append(Case("tool_call_named_stream", tool_payload, True, validate_tool_expected))

    return cases


def run_case(base_url: str, case: Case, timeout: int) -> dict[str, Any]:
    started = time.time()
    try:
        raw = (
            post_stream(base_url, case.payload, timeout=timeout)
            if case.stream
            else post_json(base_url, case.payload, timeout=timeout)
        )
        elapsed = time.time() - started
        if not raw["ok"]:
            return {
                "ok": False,
                "api_ok": False,
                "elapsed_sec": elapsed,
                "status": raw.get("status"),
                "error": raw.get("body"),
            }
        body = raw["body"]
        valid, reason, normalized = case.validator(body)
        return {
            "ok": bool(valid),
            "api_ok": True,
            "elapsed_sec": elapsed,
            "status": raw.get("status"),
            "reason": reason,
            "normalized": normalized,
            "finish_reason": (body.get("choices") or [{}])[0].get("finish_reason"),
            "usage": body.get("usage"),
            "raw": body,
        }
    except Exception as exc:
        return {
            "ok": False,
            "api_ok": False,
            "elapsed_sec": time.time() - started,
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }


def classify_pair(stock: dict[str, Any], candidate: dict[str, Any]) -> str:
    if stock["ok"] and candidate["ok"]:
        return "both_pass"
    if stock["ok"] and not candidate["ok"]:
        return "candidate_regression"
    if not stock["ok"] and candidate["ok"]:
        return "candidate_only_pass"
    return "both_fail"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-url", required=True)
    parser.add_argument("--candidate-url", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = build_cases()
    results: dict[str, Any] = {
        "schema": "vllm_cc_correctness_validation.v1",
        "stock_url": args.stock_url,
        "candidate_url": args.candidate_url,
        "cases": {},
    }
    regressions: list[str] = []
    both_fail: list[str] = []

    for case in cases:
        print(f"running {case.name}", flush=True)
        stock = run_case(args.stock_url, case, args.timeout)
        candidate = run_case(args.candidate_url, case, args.timeout)
        classification = classify_pair(stock, candidate)
        if classification == "candidate_regression":
            regressions.append(case.name)
        if classification == "both_fail":
            both_fail.append(case.name)
        results["cases"][case.name] = {
            "classification": classification,
            "stock": stock,
            "candidate": candidate,
        }
        (out_dir / f"{case.name}.json").write_text(
            json.dumps(results["cases"][case.name], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    summary = {
        "total_cases": len(cases),
        "both_pass": sum(
            1 for c in results["cases"].values() if c["classification"] == "both_pass"
        ),
        "candidate_regressions": regressions,
        "both_fail": both_fail,
        "candidate_only_pass": [
            name
            for name, c in results["cases"].items()
            if c["classification"] == "candidate_only_pass"
        ],
    }
    results["summary"] = summary
    (out_dir / "correctness-results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)

    if regressions:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
