#!/usr/bin/env python3
"""Property test for deterministic block-table dirty-update coalescing."""

from __future__ import annotations

import argparse
import json
import random
from types import SimpleNamespace

import numpy as np

from vllm.v1.worker.block_table import BlockTable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260722)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    for case_number in range(args.cases):
        row_count = 8
        column_count = 32
        initial = np.arange(row_count * column_count, dtype=np.int32).reshape(
            row_count, column_count
        )
        final = initial.copy()

        block_table = BlockTable.__new__(BlockTable)
        block_table._dirty_rows = []
        block_table._dirty_starts = []
        block_table._dirty_values = []
        block_table._dirty_cu_lens = []

        for _ in range(rng.randint(1, 40)):
            row = rng.randrange(row_count)
            start = rng.randrange(column_count)
            length = rng.randint(1, column_count - start)
            values = [rng.randrange(100_000) for _ in range(length)]
            final[row, start : start + length] = values
            block_table._dirty_rows.append(row)
            block_table._dirty_starts.append(start)
            block_table._dirty_values.extend(values)
            block_table._dirty_cu_lens.append(len(block_table._dirty_values))

        block_table.block_table = SimpleNamespace(np=final)
        rows, starts, values, cumulative_lengths = block_table._coalesce_dirty_updates()

        reconstructed = initial.copy()
        previous_length = 0
        written: dict[int, set[int]] = {}
        for row, start, cumulative_length in zip(rows, starts, cumulative_lengths):
            length = cumulative_length - previous_length
            destinations = range(start, start + length)
            row_written = written.setdefault(row, set())
            assert row_written.isdisjoint(destinations), case_number
            row_written.update(destinations)
            reconstructed[row, start : start + length] = values[
                previous_length:cumulative_length
            ]
            previous_length = cumulative_length

        assert np.array_equal(reconstructed, final), case_number

    print(
        json.dumps(
            {
                "cases": args.cases,
                "seed": args.seed,
                "status": "pass",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
