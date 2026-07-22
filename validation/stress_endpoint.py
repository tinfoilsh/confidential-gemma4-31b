#!/usr/bin/env python3
"""Stress deterministic API behavior while request slots are reused."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import sys
from pathlib import Path
from typing import Any

from validate_stock_candidate_cc import Case, build_cases, run_case


def stable_projection(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("ok"),
        "api_ok": result.get("api_ok"),
        "status": result.get("status"),
        "normalized": result.get("normalized"),
        "finish_reason": result.get("finish_reason"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument("--requests-per-case", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260722)
    args = parser.parse_args()

    if args.requests_per_case < 1:
        parser.error("--requests-per-case must be at least 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    cases = build_cases()
    oracles: dict[str, dict[str, Any]] = {}
    for case in cases:
        print(f"building serial oracle: {case.name}", flush=True)
        result = run_case(args.url, case, args.timeout)
        oracles[case.name] = stable_projection(result)

    jobs: list[tuple[int, Case]] = []
    for case in cases:
        jobs.extend((repeat, case) for repeat in range(args.requests_per_case))
    random.Random(args.seed).shuffle(jobs)

    results: list[dict[str, Any]] = []

    def run_job(sequence: int, repeat: int, case: Case) -> dict[str, Any]:
        result = run_case(args.url, case, args.timeout)
        projection = stable_projection(result)
        return {
            "sequence": sequence,
            "repeat": repeat,
            "case": case.name,
            "matches_oracle": projection == oracles[case.name],
            "projection": projection,
            "result": result,
        }

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.concurrency
    ) as executor:
        futures = [
            executor.submit(run_job, sequence, repeat, case)
            for sequence, (repeat, case) in enumerate(jobs)
        ]
        for completed, future in enumerate(
            concurrent.futures.as_completed(futures), start=1
        ):
            results.append(future.result())
            if completed % args.concurrency == 0 or completed == len(futures):
                print(f"completed {completed}/{len(futures)}", flush=True)

    results.sort(key=lambda result: result["sequence"])
    failed = [
        result["sequence"]
        for result in results
        if not result["result"].get("ok")
    ]
    mismatched = [
        result["sequence"] for result in results if not result["matches_oracle"]
    ]
    summary = {
        "total_requests": len(results),
        "concurrency": args.concurrency,
        "requests_per_case": args.requests_per_case,
        "failed_requests": failed,
        "oracle_mismatches": mismatched,
    }
    document = {
        "schema": "vllm_cc_endpoint_stress.v1",
        "url": args.url,
        "seed": args.seed,
        "oracles": oracles,
        "summary": summary,
        "results": results,
    }
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if not failed and not mismatched else 2


if __name__ == "__main__":
    sys.exit(main())
