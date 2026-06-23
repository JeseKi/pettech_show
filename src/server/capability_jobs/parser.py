# -*- coding: utf-8 -*-
"""Parse generic capability job results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import CapabilityResultOut


def parse_capability_result(
    *,
    job_id: str,
    capability_key: str,
    workdir: Path,
    markdown_path: str | None,
    json_path: str | None,
    summary: dict[str, Any],
) -> CapabilityResultOut:
    if not markdown_path:
        raise FileNotFoundError("任务未生成 Markdown 结果")
    if not json_path:
        raise FileNotFoundError("任务未生成 JSON 结果")

    md_file = workdir / markdown_path
    json_file = workdir / json_path
    if not md_file.is_file():
        raise FileNotFoundError("Markdown 结果不存在")
    if not json_file.is_file():
        raise FileNotFoundError("JSON 结果不存在")
    parsed = json.loads(json_file.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("JSON 结果必须是对象")
    return CapabilityResultOut(
        job_id=job_id,
        capability_key=capability_key,
        markdown=md_file.read_text(encoding="utf-8", errors="replace"),
        data=parsed,
        summary=summary,
    )
