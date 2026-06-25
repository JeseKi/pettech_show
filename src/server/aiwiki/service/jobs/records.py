# -*- coding: utf-8 -*-
"""AI Wiki manifest synchronization and startup recovery."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.server.config import global_config

from ...dao import AiwikiJobDAO
from ...parser import parse_aiwiki_result
from ..persistence import (
    manifest_db_payload,
    read_manifest,
    write_manifest,
)
from ..progress import progress_marked_complete
from .access import default_admin_user_id


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return

    dao = AiwikiJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_aiwiki/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 AI Wiki manifest {}: {}", manifest_path, exc)
            continue

        status_value = str(manifest.get("status") or "")
        if status_value in {"queued", "running"}:
            manifest = _recover_interrupted_manifest(workdir, manifest)
            write_manifest(workdir, manifest)

        if dao.get(str(manifest.get("id"))) is None:
            manifest.setdefault("owner_user_id", default_admin_user_id(db))
            dao.upsert_from_payload(manifest_db_payload(workdir, manifest))
        elif status_value in {"queued", "running"}:
            dao.upsert_from_payload(manifest_db_payload(workdir, manifest))


def _recover_interrupted_manifest(
    workdir: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    recovered = dict(manifest)
    if progress_marked_complete(workdir):
        try:
            result = parse_aiwiki_result(str(recovered.get("id") or workdir.name), workdir)
            if result.materials or result.wiki_entries:
                recovered.update(
                    {
                        "status": "completed",
                        "message": "AI Wiki 生成完成（服务启动时恢复）",
                        "finished_at": recovered.get("finished_at")
                        or datetime.now(timezone.utc).isoformat(),
                        "summary": result.summary,
                    }
                )
                return recovered
        except Exception as exc:
            logger.warning("恢复 AI Wiki 完成任务失败 {}: {}", workdir, exc)

    recovered.update(
        {
            "status": "failed",
            "message": "任务因服务重启中断，请重新提交",
            "finished_at": recovered.get("finished_at")
            or datetime.now(timezone.utc).isoformat(),
        }
    )
    return recovered
