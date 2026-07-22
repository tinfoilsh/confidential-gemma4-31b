#!/usr/bin/env python3
"""Run the Gemma API correctness suite repeatedly against one endpoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validate_stock_candidate_cc import build_cases, run_case


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
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be at least 1")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    results: dict[str, Any] = {
        "schema": "vllm_cc_endpoint_validation.v1",
        "label": args.label,
        "url": args.url,
        "requested_runs": args.runs,
        "cases": {},
    }

    failed: list[str] = []
    nondeterministic: list[str] = []
    for case in cases:
        case_runs: list[dict[str, Any]] = []
        for run_number in range(1, args.runs + 1):
            print(f"running {case.name} ({run_number}/{args.runs})", flush=True)
            result = run_case(args.url, case, args.timeout)
            result["run_number"] = run_number
            case_runs.append(result)

        projections = [stable_projection(result) for result in case_runs]
        all_passed = all(bool(result.get("ok")) for result in case_runs)
        deterministic = all(
            projection == projections[0] for projection in projections[1:]
        )
        if not all_passed:
            failed.append(case.name)
        if not deterministic:
            nondeterministic.append(case.name)

        case_result = {
            "all_passed": all_passed,
            "deterministic": deterministic,
            "stable_projection": projections[0],
            "runs": case_runs,
        }
        results["cases"][case.name] = case_result
        (out_dir / f"{case.name}.json").write_text(
            json.dumps(case_result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    summary = {
        "total_cases": len(cases),
        "total_requests": len(cases) * args.runs,
        "passed_cases": len(cases) - len(failed),
        "failed_cases": failed,
        "nondeterministic_cases": nondeterministic,
    }
    results["summary"] = summary
    (out_dir / "endpoint-validation.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if not failed and not nondeterministic else 2


if __name__ == "__main__":
    sys.exit(main())
