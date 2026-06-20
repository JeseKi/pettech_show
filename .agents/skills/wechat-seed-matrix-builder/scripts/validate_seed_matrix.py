#!/usr/bin/env python3
"""Validate a WeChat article seed matrix CSV."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


REQUIRED_FIELDS = [
    "day",
    "slot",
    "seed_id",
    "content_pool",
    "topic",
    "pain_point",
    "solution",
    "hook",
    "mother_topic_prompt",
    "variant_ids_to_generate",
    "expected_article_count",
    "primary_account_type",
    "backup_account_types",
    "hook_package",
    "primary_hook_ids",
    "cta_strategy",
    "publishing_note",
]

REQUIRED_NONEMPTY = [
    "day",
    "slot",
    "seed_id",
    "content_pool",
    "topic",
    "pain_point",
    "solution",
    "hook",
    "mother_topic_prompt",
    "variant_ids_to_generate",
    "expected_article_count",
    "primary_account_type",
    "backup_account_types",
    "cta_strategy",
    "publishing_note",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-table", required=True, help="seed matrix CSV to validate")
    parser.add_argument("--min-rows", type=int, default=1, help="minimum expected row count")
    return parser.parse_args()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def validate(path: Path, min_rows: int) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"CSV 不存在：{path}"]

    fieldnames, rows = read_rows(path)
    missing_fields = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    if missing_fields:
        errors.append(f"缺少字段：{', '.join(missing_fields)}")
    if len(rows) < min_rows:
        errors.append(f"行数不足：{len(rows)} < {min_rows}")

    seen_seeds: set[str] = set()
    for i, row in enumerate(rows, start=2):
        for field in REQUIRED_NONEMPTY:
            if not (row.get(field) or "").strip():
                errors.append(f"第 {i} 行 {field} 为空")
        seed_id = (row.get("seed_id") or "").strip()
        if seed_id:
            if not re.fullmatch(r"S\d+", seed_id):
                errors.append(f"第 {i} 行 seed_id 格式错误：{seed_id}")
            if seed_id in seen_seeds:
                errors.append(f"重复 seed_id：{seed_id}")
            seen_seeds.add(seed_id)
        variants = [item for item in (row.get("variant_ids_to_generate") or "").split("|") if item]
        if not variants:
            errors.append(f"第 {i} 行 variant_ids_to_generate 为空")
        elif any(not re.fullmatch(r"V\d+", item) for item in variants):
            errors.append(f"第 {i} 行 variant_ids_to_generate 格式异常：{row.get('variant_ids_to_generate')}")
        expected = (row.get("expected_article_count") or "").strip()
        if expected and not expected.isdigit():
            errors.append(f"第 {i} 行 expected_article_count 不是数字：{expected}")
    return errors


def main() -> None:
    args = parse_args()
    path = Path(args.source_table)
    errors = validate(path, args.min_rows)
    if errors:
        print(f"FAIL {path}")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    _, rows = read_rows(path)
    print(f"OK {path} rows={len(rows)}")


if __name__ == "__main__":
    main()
