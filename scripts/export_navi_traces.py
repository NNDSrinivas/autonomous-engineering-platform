#!/usr/bin/env python3
"""Export NAVI trace events from JSONL with simple filters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export NAVI traces to JSONL")
    parser.add_argument(
        "--input",
        default="data/navi_traces.jsonl",
        help="Input JSONL trace file (default: data/navi_traces.jsonl)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSONL path",
    )
    parser.add_argument(
        "--event-type",
        action="append",
        default=[],
        help="Filter by event_type (can be repeated)",
    )
    parser.add_argument(
        "--endpoint",
        action="append",
        default=[],
        help="Filter by endpoint (can be repeated)",
    )
    return parser.parse_args()


def matches_filters(record: dict[str, Any], event_types: set[str], endpoints: set[str]) -> bool:
    if event_types and record.get("event_type") not in event_types:
        return False
    if endpoints and record.get("endpoint") not in endpoints:
        return False
    return True


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise SystemExit(f"Input trace file not found: {input_path}")

    event_types = set(args.event_type)
    endpoints = set(args.endpoint)

    total = 0
    exported = 0

    with input_path.open("r", encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not matches_filters(record, event_types, endpoints):
                continue

            dst.write(json.dumps(record, ensure_ascii=True))
            dst.write("\n")
            exported += 1

    print(f"Exported {exported}/{total} records to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
