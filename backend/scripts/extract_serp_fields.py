#!/usr/bin/env python3
"""
Extract domain, type, and rank_group from a large DataForSEO-like JSON payload.

Usage:
  python extract_serp_fields.py --input sample.json --output extracted.json
  python extract_serp_fields.py --input sample.json --csv extracted.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _get_nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _domain_from_item(item: dict[str, Any]) -> str | None:
    domain = item.get("domain")
    if domain:
        return str(domain)

    # Fallback for payloads where URL exists but domain is absent.
    url = item.get("url") or item.get("breadcrumb")
    if isinstance(url, str) and "://" in url:
        host = url.split("://", 1)[1].split("/", 1)[0].strip()
        return host or None
    return None


def extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    
    # 1. Check Tasks
    tasks = payload.get("tasks", [])
    if not tasks:
        print("DEBUG: No 'tasks' found in JSON.")
        return extracted

    for t_idx, task in enumerate(tasks):
        # 2. Check Results
        results = task.get("result", [])
        if not results:
            print(f"DEBUG: Task {t_idx} has no 'result' list.")
            continue
            
        for r_idx, result in enumerate(results):
            # 3. Check Items
            items = result.get("items", [])
            if not items:
                # DATA-SPECIFIC FIX: Some regular endpoints put items 
                # inside a 'data' or 'organic' key depending on version
                print(f"DEBUG: Task {t_idx}, Result {r_idx} has no 'items' list.")
                continue
            
            print(f"DEBUG: Found {len(items)} items in Task {t_idx}, Result {r_idx}")
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                extracted.append({
                    "domain": _domain_from_item(item),
                    "type": item.get("type"),
                    "rank_group": item.get("rank_group"),
                })
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract key fields from SERP JSON.")
    parser.add_argument("--input", required=True, help="Path to source JSON file")
    parser.add_argument("--output", help="Path to output JSON file")
    parser.add_argument("--csv", help="Path to output CSV file")
    args = parser.parse_args()

    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    rows = extract_records(payload)

    if not args.output and not args.csv:
        print(json.dumps(rows, indent=2))
        return

    if args.output:
        Path(args.output).write_text(json.dumps(rows, indent=2), encoding="utf-8")

    if args.csv:
        with Path(args.csv).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["domain", "type", "rank_group"])
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
