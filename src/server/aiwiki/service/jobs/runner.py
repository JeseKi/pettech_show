# -*- coding: utf-8 -*-
"""AI Wiki background job runner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from ...parser import parse_aiwiki_result
from ..checks import python_args, run_check_command
from ..logs import append_log
from ..opencode import (
    prepare_opencode_config,
    prepare_skills,
    run_opencode,
    run_repair_opencode,
)
from ..persistence import read_manifest, update_manifest
from ..progress import (
    mark_progress_failure,
    mark_progress_running,
    progress_marked_complete,
)


def run_job(
    job_id: str, workdir: Path, session_factory: sessionmaker[Session]
) -> None:
    if not _job_can_continue(workdir):
        return
    try:
        started_at = datetime.now(timezone.utc)
        update_manifest(
            workdir,
            status="running",
            message="OpenCode 正在生成生文材料和 AI Wiki",
            started_at=started_at.isoformat(),
            session_factory=session_factory,
        )
        prepare_skills(workdir)
        prepare_opencode_config(workdir)
        _run_opencode_with_json_check(
            workdir,
            generate_search_assets=_generate_search_assets(read_manifest(workdir)),
        )
        if not _job_can_continue(workdir):
            return
        result = parse_aiwiki_result(job_id, workdir)
        if not result.materials and not result.wiki_entries:
            raise RuntimeError("OpenCode 未生成 material 或 wiki 结果")
        update_manifest(
            workdir,
            status="completed",
            message="AI Wiki 生成完成",
            finished_at=datetime.now(timezone.utc).isoformat(),
            summary=result.summary,
            session_factory=session_factory,
        )
    except Exception as exc:
        if not _job_can_continue(workdir):
            return
        logger.exception("AI Wiki job failed: {}", job_id)
        append_log(workdir, f"ERROR: {exc}")
        mark_progress_failure(workdir, str(exc))
        update_manifest(
            workdir,
            status="failed",
            message=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
            session_factory=session_factory,
        )


def _job_can_continue(workdir: Path) -> bool:
    return (workdir / "manifest.json").exists()


def _run_opencode_with_json_check(workdir: Path, *, generate_search_assets: bool) -> None:
    run_opencode(workdir, generate_search_assets=generate_search_assets)
    if not progress_marked_complete(workdir):
        raise RuntimeError("progress.json 未写入任务完成标记")
    try:
        _run_aiwiki_json_check(workdir)
        return
    except Exception as first_error:
        append_log(workdir, f"JSON CHECK ERROR: {first_error}")
        mark_progress_running(
            workdir,
            step="修复 JSON",
            summary="JSON 校验失败，正在下发 OpenCode 修复任务",
        )
        run_repair_opencode(workdir, error=str(first_error))
        if not progress_marked_complete(workdir):
            raise RuntimeError("修复后 progress.json 未写入任务完成标记")
        _run_aiwiki_json_check(workdir)


def _run_aiwiki_json_check(workdir: Path) -> None:
    run_check_command(
        workdir,
        python_args(
            ".agents/skills/wechat-raw-materializer/scripts/materialize_raw.py",
            "validate",
            "--json-only",
        ),
        label="AI Wiki JSON 校验",
    )


def _generate_search_assets(manifest: dict[str, Any]) -> bool:
    options = manifest.get("options")
    if not isinstance(options, dict):
        return True
    return bool(options.get("generate_search_assets", True))
