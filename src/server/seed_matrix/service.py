# -*- coding: utf-8 -*-
"""Public seed matrix job service functions."""

from __future__ import annotations

import os
import re
import secrets
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from math import ceil
from typing import Any

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.dao import AiwikiJobDAO
from src.server.aiwiki.service.logs import append_log, read_log_tail
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.persistence import existing_job_workdir
from src.server.aiwiki.service.progress import (
    initial_progress,
    progress_marked_complete,
    read_progress,
    write_progress,
)
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config

from .dao import SeedMatrixJobDAO, parse_json_dict
from .models import SeedMatrixJob
from .parser import parse_seed_matrix_result
from .queue_state import get_queue
from .schemas import (
    SeedMatrixCreate,
    SeedMatrixJobListOut,
    SeedMatrixJobOut,
    SeedMatrixJobSummaryOut,
    SeedMatrixResultOut,
)

SEED_MATRIX_SKILL_NAME = "wechat-seed-matrix-builder"
RESULT_CSV_PATH = "seed_matrix/seed_matrix.csv"


def create_job(
    db: Session, payload: SeedMatrixCreate, current_user: User
) -> SeedMatrixJobOut:
    source = AiwikiJobDAO(db).get(payload.source_aiwiki_job_id)
    if source is None or not _can_access_job(current_user, source.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Wiki 任务不存在")
    if source.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能选择已完成的 AI Wiki 任务",
        )

    source_workdir = existing_job_workdir(source.id, db)
    if not (source_workdir / "material").exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 任务没有 material 结果",
        )
    material_count = _material_count(source_workdir)
    if material_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 任务没有可用 material JSON",
        )

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    (workdir / "logs").mkdir(parents=True, exist_ok=False)
    write_progress(workdir, initial_progress())
    _copy_source_artifacts(source_workdir, workdir)
    _prepare_skill(workdir)

    params = _build_generation_params(payload, material_count)
    job = SeedMatrixJobDAO(db).create(
        job_id=job_id,
        owner_user_id=current_user.id,
        source_aiwiki_job_id=source.id,
        workdir=workdir.as_posix(),
        params=params,
        created_at=now,
    )
    session_factory = _build_session_factory(db)
    get_queue().enqueue(job_id, lambda: _run_job(job_id, session_factory))
    return job_out_from_model(job, current_user.username)


def list_jobs(
    db: Session,
    *,
    limit: int,
    offset: int,
    current_user: User,
    source_aiwiki_job_id: str | None = None,
) -> SeedMatrixJobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    owner_filter = None if _is_admin(current_user) else current_user.id
    dao = SeedMatrixJobDAO(db)
    jobs = dao.list(
        limit=normalized_limit,
        offset=normalized_offset,
        owner_user_id=owner_filter,
        source_aiwiki_job_id=source_aiwiki_job_id,
    )
    return SeedMatrixJobListOut(
        items=[job_summary_from_model(job, dao.owner_username(job.owner_user_id)) for job in jobs],
        total=dao.count(owner_user_id=owner_filter, source_aiwiki_job_id=source_aiwiki_job_id),
        limit=normalized_limit,
        offset=normalized_offset,
    )


def get_job(db: Session, job_id: str, current_user: User) -> SeedMatrixJobOut:
    job = _get_accessible_job(db, job_id, current_user)
    return job_out_from_model(job, SeedMatrixJobDAO(db).owner_username(job.owner_user_id))


def get_result(
    db: Session, job_id: str, current_user: User
) -> SeedMatrixResultOut:
    job = _get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return parse_seed_matrix_result(
            job_id=job.id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            workdir=Path(job.workdir),
            csv_path=job.result_csv_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    job = _get_accessible_job(db, job_id, current_user)
    if job.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务正在执行，完成或失败后才能删除",
        )
    workdir = Path(job.workdir)
    SeedMatrixJobDAO(db).delete(job)
    shutil.rmtree(workdir, ignore_errors=True)


def result_csv_file(db: Session, job_id: str, current_user: User) -> Path:
    job = _get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    if not job.result_csv_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="矩阵 CSV 不存在")
    path = Path(job.workdir) / job.result_csv_path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="矩阵 CSV 不存在")
    return path


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return
    dao = SeedMatrixJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_seed_matrix/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = _read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 Seed Matrix manifest {}: {}", manifest_path, exc)
            continue
        if dao.get(str(manifest.get("id"))) is not None:
            continue
        job = SeedMatrixJob(
            id=str(manifest["id"]),
            owner_user_id=_coerce_int(manifest.get("owner_user_id")),
            source_aiwiki_job_id=str(manifest["source_aiwiki_job_id"]),
            status=str(manifest.get("status") or "failed"),
            message=manifest.get("message"),
            workdir=workdir.as_posix(),
            params_json=_json_string(manifest.get("params") or {}),
            result_csv_path=manifest.get("result_csv_path"),
            summary_json=_json_string(manifest.get("summary") or {}),
            created_at=_coerce_datetime(manifest.get("created_at")) or datetime.now(timezone.utc),
            started_at=_coerce_datetime(manifest.get("started_at")),
            finished_at=_coerce_datetime(manifest.get("finished_at")),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()


def job_out_from_model(job: SeedMatrixJob, owner_username: str | None = None) -> SeedMatrixJobOut:
    return SeedMatrixJobOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        source_aiwiki_job_id=job.source_aiwiki_job_id,
        status=_coerce_status(job.status),
        queue_position=get_queue().queue_position(job.id),
        message=job.message,
        params=parse_json_dict(job.params_json),
        summary=parse_json_dict(job.summary_json),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=read_progress(Path(job.workdir)),
        log_tail=read_log_tail(Path(job.workdir)),
    )


def job_summary_from_model(
    job: SeedMatrixJob, owner_username: str | None = None
) -> SeedMatrixJobSummaryOut:
    return SeedMatrixJobSummaryOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        source_aiwiki_job_id=job.source_aiwiki_job_id,
        status=_coerce_status(job.status),
        message=job.message,
        params=parse_json_dict(job.params_json),
        summary=parse_json_dict(job.summary_json),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def new_job_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_seed_matrix"


def job_workdir(job_id: str) -> Path:
    return Path(global_config.project_root) / "data" / job_id


def _run_job(job_id: str, session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        job = SeedMatrixJobDAO(session).get(job_id)
        if job is None:
            return
        started_at = datetime.now(timezone.utc)
        _update_job(
            session,
            job_id,
            status="running",
            message="OpenCode 正在生成选题矩阵",
            started_at=started_at.isoformat(),
        )
        workdir = Path(job.workdir)
        _write_manifest(workdir, job)
        prepare_opencode_config(workdir)
        _run_opencode(workdir, parse_json_dict(job.params_json))
        if not progress_marked_complete(workdir):
            raise RuntimeError("progress.json 未写入任务完成标记")

        result = parse_seed_matrix_result(
            job_id=job.id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            workdir=workdir,
            csv_path=RESULT_CSV_PATH,
        )
        _update_job(
            session,
            job_id,
            status="completed",
            message="选题矩阵生成完成",
            result_csv_path=RESULT_CSV_PATH,
            summary=result.summary,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        _write_manifest(workdir, SeedMatrixJobDAO(session).get(job_id))
    except Exception as exc:
        logger.exception("Seed matrix job failed: {}", job_id)
        try:
            job = SeedMatrixJobDAO(session).get(job_id)
            if job is not None:
                append_log(Path(job.workdir), f"ERROR: {exc}")
                _update_job(
                    session,
                    job_id,
                    status="failed",
                    message=str(exc),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                _write_manifest(Path(job.workdir), SeedMatrixJobDAO(session).get(job_id))
        finally:
            pass
    finally:
        session.close()


def _run_opencode(workdir: Path, params: dict[str, Any]) -> None:
    command = shlex.split(global_config.aiwiki_opencode_command)
    if not command:
        raise RuntimeError("AIWIKI_OPENCODE_COMMAND 不能为空")
    args = [
        *command,
        "run",
        "--dir",
        workdir.as_posix(),
        "--title",
        "Seed matrix generation",
    ]
    if global_config.aiwiki_opencode_model:
        args.extend(["--model", global_config.aiwiki_opencode_model])
    if global_config.aiwiki_opencode_agent:
        args.extend(["--agent", global_config.aiwiki_opencode_agent])
    if global_config.aiwiki_opencode_extra_args:
        args.extend(shlex.split(global_config.aiwiki_opencode_extra_args))
    args.append(_build_prompt(workdir, params))

    log_path = workdir / "logs" / "opencode.log"
    append_log(workdir, "$ " + " ".join(shlex.quote(arg) for arg in args[:-1]) + " <prompt>")
    env = os.environ.copy()
    config_path = workdir / "config.json"
    if config_path.exists():
        env["OPENCODE_CONFIG"] = config_path.as_posix()
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            args,
            cwd=workdir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )
        deadline = datetime.now(timezone.utc).timestamp() + global_config.aiwiki_task_timeout_seconds
        while process.poll() is None:
            if datetime.now(timezone.utc).timestamp() > deadline:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                raise RuntimeError("OpenCode 执行超时")

            if progress_marked_complete(workdir):
                append_log(workdir, "progress.json 已标记任务完成，后端结束 OpenCode 并解析结果。")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                return

            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

        return_code = process.returncode
    if return_code != 0:
        raise RuntimeError(f"OpenCode 执行失败，退出码 {return_code}")


def _build_prompt(workdir: Path, params: dict[str, Any]) -> str:
    max_seeds = params.get("max_seeds")
    max_seeds_line = f"- max_seeds: {max_seeds}" if max_seeds else "- max_seeds: 不限制"
    hooks = str(params.get("hooks") or "")
    return f"""
你在一个隔离的选题矩阵生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`，其中 `event` 使用 `started`、`completed` 或 `failed`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `started` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的事。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `completed` 事件，`summary` 简要概括刚完成的内容。
- 所有矩阵生成和校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"completed","step":"all","summary":"任务完成"}}`。

目标：
1. 使用 $wechat-seed-matrix-builder，从当前目录的 `material/` 和 `wiki/` 生成选题矩阵 CSV。
2. 输出 CSV 必须写到：`{RESULT_CSV_PATH}`。
3. 生成后运行：
   python3 .agents/skills/wechat-seed-matrix-builder/scripts/validate_seed_matrix.py --source-table {RESULT_CSV_PATH}
4. 校验通过后直接结束，不要等待用户继续输入。

生成参数：
- material_dirs: 当前目录下所有 `material/<date>` 目录
- wiki_dir: wiki
- output_csv: {RESULT_CSV_PATH}
- start_seed: {params.get("start_seed") or "S001"}
- start_day: {params.get("start_day") or "D01"}
- slots_per_day: {params.get("slots_per_day") or 3}
- seeds_per_material: {params.get("seeds_per_material") or 1}
{max_seeds_line}
- hooks: {hooks or "留空"}
- hook_package: {params.get("hook_package") or "留空"}
- primary_hook_ids: {params.get("primary_hook_ids") or "留空"}
- expected_article_count: {params.get("expected_article_count") or 10}

要求：
- 不要覆盖当前目录外的任何文件。
- 不要重新处理 uploads/raw 原文，只使用已存在的 material/wiki 资产。
- 如果 material 有坏文件，按 skill 约束跳过并在日志里说明。
- CSV 必须包含 seed_id、topic、pain_point、solution、hook、mother_topic_prompt 等规划字段。
""".strip()


def _build_generation_params(payload: SeedMatrixCreate, material_count: int) -> dict[str, Any]:
    params = payload.model_dump()
    expected_seed_count = int(params["expected_seed_count"])
    hooks = _format_hooks(params.get("hooks") or [])
    params["start_seed"] = "S001"
    params["start_day"] = "D01"
    params["expected_article_count"] = 10
    params["max_seeds"] = expected_seed_count
    params["seeds_per_material"] = max(1, ceil(expected_seed_count / material_count))
    params["hook_package"] = hooks
    params["primary_hook_ids"] = ""
    return params


def _format_hooks(hooks: list[str]) -> str:
    cleaned = [hook.strip() for hook in hooks if hook.strip()]
    return "\n\n".join(f"Hook {index}:\n{hook}" for index, hook in enumerate(cleaned, start=1))


def _material_count(source_workdir: Path) -> int:
    return len(list((source_workdir / "material").glob("*/*.json")))


def _copy_source_artifacts(source_workdir: Path, target_workdir: Path) -> None:
    for name in ("material", "wiki"):
        source = source_workdir / name
        if source.exists():
            shutil.copytree(source, target_workdir / name, ignore=shutil.ignore_patterns("__pycache__"))


def _prepare_skill(workdir: Path) -> None:
    source_root = Path(global_config.project_root) / ".agents" / "skills"
    source = source_root / SEED_MATRIX_SKILL_NAME
    if not source.exists():
        raise RuntimeError(f"Skill 不存在：{source}")
    target = workdir / ".agents" / "skills" / SEED_MATRIX_SKILL_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def _get_accessible_job(db: Session, job_id: str, current_user: User) -> SeedMatrixJob:
    if not re.fullmatch(r"\d{14}_[a-f0-9]{8}_seed_matrix", job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    job = SeedMatrixJobDAO(db).get(job_id)
    if job is None or not _can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


def _update_job(session: Session, job_id: str, **fields: Any) -> None:
    SeedMatrixJobDAO(session).update(job_id, **fields)


def _build_session_factory(db: Session) -> sessionmaker[Session]:
    bind = db.get_bind()
    if isinstance(bind, Connection):
        bind = bind.engine
    if not isinstance(bind, Engine):
        raise RuntimeError("无法创建选题矩阵任务会话工厂")
    return sessionmaker(bind=bind, autocommit=False, autoflush=False)


def _read_manifest(workdir: Path) -> dict[str, Any]:
    import json

    return json.loads((workdir / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(workdir: Path, job: SeedMatrixJob | None) -> None:
    if job is None:
        return
    import json

    payload = {
        "id": job.id,
        "owner_user_id": job.owner_user_id,
        "source_aiwiki_job_id": job.source_aiwiki_job_id,
        "status": job.status,
        "message": job.message,
        "workdir": job.workdir,
        "params": parse_json_dict(job.params_json),
        "result_csv_path": job.result_csv_path,
        "summary": parse_json_dict(job.summary_json),
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
    tmp_path = workdir / "manifest.json.tmp"
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, workdir / "manifest.json")


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def _can_access_job(user: User, owner_user_id: int | None) -> bool:
    return _is_admin(user) or owner_user_id == user.id


def _coerce_status(value: str) -> Any:
    if value not in {"queued", "running", "completed", "failed"}:
        return "failed"
    return value


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _json_string(value: Any) -> str:
    import json

    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
