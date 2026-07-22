#!/usr/bin/env python3
"""Exercise public-input security boundaries against a running candidate."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import struct
import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from typing import Any


MODEL = "gemma4-31b"


def png_data_url() -> str:
    """Return a dependency-free 32x32 RGB PNG data URL."""
    width = height = 32
    rows = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def request(
    base_url: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    headers = {"accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                body: Any = json.loads(raw)
            except json.JSONDecodeError:
                body = raw
            return {"status": response.status, "body": body}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return {"status": exc.code, "body": body}
    except Exception as exc:
        return {"status": None, "error": f"{type(exc).__name__}: {exc}"}


def chat_payload(content: Any, *, max_tokens: int = 8) -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "reasoning_effort": "none",
        "include_reasoning": False,
    }


def rejection_cases() -> list[tuple[str, str, dict[str, Any]]]:
    regex = chat_payload("Reply with lowercase letters only.")
    regex["structured_outputs"] = {"regex": "(a+)+$"}
    return [
        ("regex_disabled", "/v1/chat/completions", regex),
        (
            "remote_image_ssrf_blocked",
            "/v1/chat/completions",
            chat_payload(
                [
                    {"type": "text", "text": "Describe this image."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "http://127.0.0.1:8001/health"},
                    },
                ]
            ),
        ),
        (
            "local_file_image_blocked",
            "/v1/chat/completions",
            chat_payload(
                [
                    {"type": "text", "text": "Describe this image."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "file:///etc/passwd"},
                    },
                ]
            ),
        ),
        (
            "video_disabled",
            "/v1/chat/completions",
            chat_payload(
                [
                    {"type": "text", "text": "Describe this video."},
                    {
                        "type": "video_url",
                        "video_url": {"url": "data:video/mp4;base64,AAAA"},
                    },
                ]
            ),
        ),
        (
            "negative_prompt_token_rejected",
            "/v1/completions",
            {
                "model": MODEL,
                "prompt": [-2],
                "temperature": 0.0,
                "max_tokens": 1,
            },
        ),
    ]


def cancel_stream(
    base_url: str,
    token: str | None,
    timeout: int,
    sequence: int,
) -> dict[str, Any]:
    payload = chat_payload(
        f"CANARY_SECURITY_{sequence:04d}: count slowly from 1 to 200.",
        max_tokens=256,
    )
    payload["stream"] = True
    headers = {
        "accept": "text/event-stream",
        "content-type": "application/json",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            for raw in response:
                if raw.startswith(b"data:"):
                    return {"sequence": sequence, "status": response.status}
            return {
                "sequence": sequence,
                "status": response.status,
                "error": "stream ended before first event",
            }
    except Exception as exc:
        return {
            "sequence": sequence,
            "status": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def response_text(result: dict[str, Any]) -> str:
    body = result.get("body")
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument("--token")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--cancel-requests", type=int, default=32)
    parser.add_argument("--cancel-concurrency", type=int, default=16)
    args = parser.parse_args()

    if args.cancel_requests < 1 or args.cancel_concurrency < 1:
        parser.error("cancellation counts must be positive")

    results: dict[str, Any] = {
        "schema": "vllm_cc_security_endpoint.v1",
        "url": args.url,
        "checks": {},
    }
    failures: list[str] = []

    health = request(args.url, "/health", token=args.token, timeout=args.timeout)
    health["passed"] = health.get("status") == 200
    results["checks"]["initial_health"] = health
    if not health["passed"]:
        failures.append("initial_health")

    for name, path, payload in rejection_cases():
        result = request(
            args.url,
            path,
            payload=payload,
            token=args.token,
            timeout=args.timeout,
        )
        result["passed"] = result.get("status") in {400, 403, 422}
        results["checks"][name] = result
        if not result["passed"]:
            failures.append(name)

        post_health = request(
            args.url, "/health", token=args.token, timeout=args.timeout
        )
        post_health["passed"] = post_health.get("status") == 200
        health_name = f"health_after_{name}"
        results["checks"][health_name] = post_health
        if not post_health["passed"]:
            failures.append(health_name)

    image = request(
        args.url,
        "/v1/chat/completions",
        payload=chat_payload(
            [
                {
                    "type": "text",
                    "text": (
                        "What is the dominant color in this image? "
                        "Reply with one uppercase color word."
                    ),
                },
                {"type": "image_url", "image_url": {"url": png_data_url()}},
            ]
        ),
        token=args.token,
        timeout=args.timeout,
    )
    image_text = response_text(image)
    image["passed"] = image.get("status") == 200 and "red" in image_text.lower()
    results["checks"]["inline_image_supported"] = image
    if not image["passed"]:
        failures.append("inline_image_supported")

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.cancel_concurrency
    ) as executor:
        cancellations = list(
            executor.map(
                lambda sequence: cancel_stream(
                    args.url, args.token, args.timeout, sequence
                ),
                range(args.cancel_requests),
            )
        )
    cancellation_errors = [item for item in cancellations if item.get("status") != 200]
    results["checks"]["cancellation_churn"] = {
        "passed": not cancellation_errors,
        "requests": args.cancel_requests,
        "concurrency": args.cancel_concurrency,
        "errors": cancellation_errors,
    }
    if cancellation_errors:
        failures.append("cancellation_churn")

    final_response = request(
        args.url,
        "/v1/chat/completions",
        payload=chat_payload("Reply with exactly SECURITY_OK.", max_tokens=16),
        token=args.token,
        timeout=args.timeout,
    )
    final_text = response_text(final_response)
    final_response["passed"] = (
        final_response.get("status") == 200
        and "SECURITY_OK" in final_text
        and "CANARY_SECURITY_" not in final_text
    )
    results["checks"]["post_cancellation_canary"] = final_response
    if not final_response["passed"]:
        failures.append("post_cancellation_canary")

    results["summary"] = {
        "total_checks": len(results["checks"]),
        "failed_checks": failures,
        "passed": not failures,
    }
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(results["summary"], indent=2, sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
