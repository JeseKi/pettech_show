# -*- coding: utf-8 -*-
"""Parse generated seed matrix CSV files."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .schemas import SeedMatrixResultOut


def parse_seed_matrix_result(
    *, job_id: str, source_aiwiki_job_id: str, workdir: Path, csv_path: str | None
) -> SeedMatrixResultOut:
    if not csv_path:
        raise FileNotFoundError("矩阵 CSV 尚未生成")
    path = workdir / csv_path
    if not path.is_file():
        raise FileNotFoundError(f"矩阵 CSV 不存在：{csv_path}")
    columns, rows = _read_csv(path)
    return SeedMatrixResultOut(
        job_id=job_id,
        source_aiwiki_job_id=source_aiwiki_job_id,
        csv_path=csv_path,
        columns=columns,
        rows=rows,
        summary=build_summary(rows),
    )


def build_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    seed_ids = [row.get("seed_id", "").strip() for row in rows if row.get("seed_id", "").strip()]
    days = {row.get("day", "").strip() for row in rows if row.get("day", "").strip()}
    account_types = {
        row.get("primary_account_type", "").strip()
        for row in rows
        if row.get("primary_account_type", "").strip()
    }
    content_pools = {
        row.get("content_pool", "").strip()
        for row in rows
        if row.get("content_pool", "").strip()
    }
    expected_total = 0
    for row in rows:
        try:
            expected_total += int(row.get("expected_article_count", "0").strip() or "0")
        except ValueError:
            continue
    return {
        "row_count": len(rows),
        "seed_count": len(seed_ids),
        "seed_range": f"{seed_ids[0]}..{seed_ids[-1]}" if seed_ids else "",
        "day_count": len(days),
        "expected_article_total": expected_total,
        "account_type_count": len(account_types),
        "content_pool_count": len(content_pools),
    }


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        rows = [
            {key: value or "" for key, value in row.items() if key is not None}
            for row in reader
        ]
    return columns, rows
