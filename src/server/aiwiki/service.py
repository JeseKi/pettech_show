# -*- coding: utf-8 -*-
"""AI Wiki job service."""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from src.server.config import global_config
from src.server.database import SessionLocal

from .dao import AiwikiJobDAO
from .models import AiwikiJob
from .parser import parse_aiwiki_result
from .queue import AiwikiJobQueue
from .schemas import (
    AiwikiResultOut,
    JobListOut,
    JobOut,
    JobStatus,
    JobSummaryOut,
    UploadedFileOut,
)

ALLOWED_EXTENSIONS = {".md", ".txt", ".docx"}
LOG_TAIL_LINES = 80
PROGRESS_FILE_NAME = "progress.json"
PROGRESS_COMPLETE_EVENT = {
    "event": "completed",
    "step": "all",
    "summary": "任务完成",
}
SKILL_SOURCES = [
    Path("/home/jese--ki/Projects/writing/.agents/skills/wechat-raw-materializer"),
    Path("/home/jese--ki/Projects/writing/.agents/skills/wechat-topic-wiki"),
]

_QUEUE: AiwikiJobQueue | None = None


def get_queue() -> AiwikiJobQueue:
    global _QUEUE
    if _QUEUE is None:
        _QUEUE = AiwikiJobQueue(max_workers=global_config.aiwiki_max_concurrent)
    return _QUEUE


def reset_queue_for_tests() -> None:
    global _QUEUE
    if _QUEUE is not None:
        _QUEUE.shutdown()
    _QUEUE = None


async def create_job(db: Session, files: list[UploadFile]) -> JobOut:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少上传一个文件",
        )

    now = datetime.now(timezone.utc)
    job_id = _new_job_id(now)
    workdir = _job_workdir(job_id)
    uploads_dir = workdir / "uploads"
    raw_date = now.strftime("%y%m%d")
    raw_dir = workdir / "raw" / raw_date
    logs_dir = workdir / "logs"
    uploads_dir.mkdir(parents=True, exist_ok=False)
    raw_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    total_size = 0
    saved_files: list[dict[str, Any]] = []
    max_bytes = global_config.aiwiki_max_upload_mb * 1024 * 1024

    for index, file in enumerate(files, start=1):
        original_name = _safe_filename(file.filename or f"upload-{index}.txt")
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型：{extension or original_name}",
            )

        content = await file.read()
        total_size += len(content)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"上传总大小不能超过 {global_config.aiwiki_max_upload_mb}MB",
            )

        upload_path = uploads_dir / original_name
        upload_path.write_bytes(content)
        raw_text = _convert_to_markdown(upload_path, content, extension)
        raw_name = f"{raw_date}_{index}_{Path(original_name).stem}.md"
        raw_path = raw_dir / _safe_filename(raw_name)
        raw_path.write_text(raw_text, encoding="utf-8")
        saved_files.append(
            {
                "filename": original_name,
                "size_bytes": len(content),
                "raw_path": raw_path.relative_to(workdir).as_posix(),
            }
        )

    manifest = {
        "id": job_id,
        "status": "queued",
        "message": "任务已进入队列",
        "created_at": now.isoformat(),
        "started_at": None,
        "finished_at": None,
        "workdir": workdir.as_posix(),
        "files": saved_files,
        "raw_date": raw_date,
    }
    _write_progress(workdir, _initial_progress())
    _write_manifest(workdir, manifest)
    _upsert_job_from_manifest(db, workdir, manifest)
    session_factory = _build_session_factory(db)
    get_queue().enqueue(job_id, lambda: _run_job(job_id, workdir, session_factory))
    return _job_out_from_manifest(workdir, manifest)


def list_jobs(db: Session, *, limit: int, offset: int) -> JobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    dao = AiwikiJobDAO(db)
    items = [
        _job_summary_from_model(job)
        for job in dao.list(limit=normalized_limit, offset=normalized_offset)
    ]
    return JobListOut(
        items=items,
        total=dao.count(),
        limit=normalized_limit,
        offset=normalized_offset,
    )


def get_job(db: Session, job_id: str) -> JobOut:
    workdir = _existing_job_workdir(job_id, db)
    manifest = _read_manifest(workdir)
    if AiwikiJobDAO(db).get(job_id) is None:
        _upsert_job_from_manifest(db, workdir, manifest)
    return _job_out_from_manifest(workdir, manifest)


def get_result(db: Session, job_id: str) -> AiwikiResultOut:
    workdir = _existing_job_workdir(job_id, db)
    manifest = _read_manifest(workdir)
    if manifest.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务尚未完成",
        )
    result = parse_aiwiki_result(job_id, workdir)
    if not result.materials and not result.wiki_entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务未生成可展示结果",
        )
    return result


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return

    dao = AiwikiJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_aiwiki/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = _read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 AI Wiki manifest {}: {}", manifest_path, exc)
            continue

        status_value = str(manifest.get("status") or "")
        if status_value in {"queued", "running"}:
            manifest = _recover_interrupted_manifest(workdir, manifest)
            _write_manifest(workdir, manifest)

        if dao.get(str(manifest.get("id"))) is None:
            dao.upsert_from_payload(_manifest_db_payload(workdir, manifest))
        elif status_value in {"queued", "running"}:
            dao.upsert_from_payload(_manifest_db_payload(workdir, manifest))


def _run_job(
    job_id: str, workdir: Path, session_factory: sessionmaker[Session]
) -> None:
    started_at = datetime.now(timezone.utc)
    _update_manifest(
        workdir,
        status="running",
        message="OpenCode 正在生成生文材料和 AI Wiki",
        started_at=started_at.isoformat(),
        session_factory=session_factory,
    )
    try:
        _prepare_skills(workdir)
        _run_opencode(workdir)
        if not _progress_marked_complete(workdir):
            raise RuntimeError("progress.json 未写入任务完成标记")
        result = parse_aiwiki_result(job_id, workdir)
        if not result.materials and not result.wiki_entries:
            raise RuntimeError("OpenCode 未生成 material 或 wiki 结果")
        _update_manifest(
            workdir,
            status="completed",
            message="AI Wiki 生成完成",
            finished_at=datetime.now(timezone.utc).isoformat(),
            summary=result.summary,
            session_factory=session_factory,
        )
    except Exception as exc:
        logger.exception("AI Wiki job failed: {}", job_id)
        _append_log(workdir, f"ERROR: {exc}")
        _update_manifest(
            workdir,
            status="failed",
            message=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
            session_factory=session_factory,
        )


def _prepare_skills(workdir: Path) -> None:
    target_root = workdir / ".agents" / "skills"
    target_root.mkdir(parents=True, exist_ok=True)
    for source in SKILL_SOURCES:
        if not source.exists():
            raise RuntimeError(f"Skill 不存在：{source}")
        target = target_root / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def _run_opencode(workdir: Path) -> None:
    command = shlex.split(global_config.aiwiki_opencode_command)
    if not command:
        raise RuntimeError("AIWIKI_OPENCODE_COMMAND 不能为空")

    args = [
        *command,
        "run",
        "--dir",
        workdir.as_posix(),
        "--title",
        "AI Wiki materialization",
    ]
    if global_config.aiwiki_opencode_model:
        args.extend(["--model", global_config.aiwiki_opencode_model])
    if global_config.aiwiki_opencode_agent:
        args.extend(["--agent", global_config.aiwiki_opencode_agent])
    if global_config.aiwiki_opencode_extra_args:
        args.extend(shlex.split(global_config.aiwiki_opencode_extra_args))
    args.append(_build_prompt(workdir))

    log_path = workdir / "logs" / "opencode.log"
    _append_log(workdir, "$ " + " ".join(shlex.quote(arg) for arg in args[:-1]) + " <prompt>")
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            args,
            cwd=workdir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
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

            if _progress_marked_complete(workdir):
                _append_log(workdir, "progress.json 已标记任务完成，后端结束 OpenCode 并解析结果。")
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


def _build_prompt(workdir: Path) -> str:
    return f"""
你在一个隔离的 AI Wiki 生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`，其中 `event` 使用 `started`、`completed` 或 `failed`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `started` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的事。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `completed` 事件，`summary` 简要概括刚完成的内容。
- 所有 material、wiki、校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"completed","step":"all","summary":"任务完成"}}`。

目标：
1. 使用 $wechat-raw-materializer 将 raw/<date>/*.md 转成 material/<date>/*.json。
2. 使用 $wechat-topic-wiki 将 material/、raw/ 中的热点、痛点、解决方案、选题、搜索入口沉淀到 wiki/。
3. 生成或更新 wiki/index.md 和 wiki/log.md。
4. 完成后运行：
   python3 .agents/skills/wechat-raw-materializer/scripts/materialize_raw.py validate --strict-search-intents --strict-question-topics
5. 所有内容生成完以后直接结束，不要等待用户继续输入。

要求：
- material JSON 必须包含 热点、痛点、解决方案、关键词/搜索入口、选题、总结。
- wiki 不复制全文，只沉淀可复用资产。
- wiki 相关输出必须落在当前目录的 wiki/ 下，不要写到裸的 topics/、solutions/ 等根目录。
- 如果 material 包含 搜索入口，必须创建或更新 wiki/search-intents/ 下的关键词池词条。
- 输出必须落在当前目录的 material/ 和 wiki/ 下。
""".strip()


def _convert_to_markdown(path: Path, content: bytes, extension: str) -> str:
    if extension == ".docx":
        return _extract_docx_text(path).strip() + "\n"
    return content.decode("utf-8", errors="replace").strip() + "\n"


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DOCX 文件无法读取：{path.name}",
        ) from exc

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [
            node.text or ""
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def _job_out_from_manifest(workdir: Path, manifest: dict[str, Any]) -> JobOut:
    payload = dict(manifest)
    payload["queue_position"] = get_queue().queue_position(manifest["id"])
    payload["progress"] = _read_progress(workdir)
    payload["log_tail"] = _read_log_tail(workdir)
    return JobOut.model_validate(payload)


def _initial_progress() -> dict[str, Any]:
    return {
        "status": "queued",
        "current_step": "任务排队中",
        "events": [
            {
                "event": "started",
                "step": "queued",
                "summary": "任务已进入队列",
            }
        ],
    }


def _progress_marked_complete(workdir: Path) -> bool:
    progress = _read_progress(workdir)
    events = progress.get("events")
    if (
        progress.get("status") != "completed"
        or progress.get("current_step") != "任务完成"
        or not isinstance(events, list)
        or not events
        or not isinstance(events[-1], dict)
    ):
        return False
    return all(events[-1].get(key) == value for key, value in PROGRESS_COMPLETE_EVENT.items())


def _read_progress(workdir: Path) -> dict[str, Any]:
    progress_path = workdir / PROGRESS_FILE_NAME
    if not progress_path.exists():
        return {}
    try:
        parsed = json.loads(
            progress_path.read_text(encoding="utf-8", errors="replace")
        )
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _write_progress(workdir: Path, progress: dict[str, Any]) -> None:
    progress_path = workdir / PROGRESS_FILE_NAME
    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _job_summary_from_model(job: AiwikiJob) -> JobSummaryOut:
    return JobSummaryOut(
        id=job.id,
        status=_coerce_job_status(job.status),
        message=job.message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        files=_parse_uploaded_files(job.files_json),
        summary=_parse_json_dict(job.summary_json),
    )


def _new_job_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_aiwiki"


def _job_workdir(job_id: str) -> Path:
    return Path(global_config.project_root) / "data" / job_id


def _existing_job_workdir(job_id: str, db: Session | None = None) -> Path:
    if not re.fullmatch(r"\d{14}_[a-f0-9]{8}_aiwiki", job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    workdir = None
    if db is not None:
        job = AiwikiJobDAO(db).get(job_id)
        if job is not None:
            workdir = Path(job.workdir)
    workdir = workdir or _job_workdir(job_id)
    if not (workdir / "manifest.json").exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return workdir


def _read_manifest(workdir: Path) -> dict[str, Any]:
    return json.loads((workdir / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(workdir: Path, manifest: dict[str, Any]) -> None:
    path = workdir / "manifest.json"
    tmp_path = workdir / "manifest.json.tmp"
    tmp_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def _update_manifest(
    workdir: Path,
    *,
    session_factory: sessionmaker[Session] | None = None,
    **fields: Any,
) -> None:
    manifest = _read_manifest(workdir)
    manifest.update(fields)
    _write_manifest(workdir, manifest)
    _upsert_job_from_manifest(
        None, workdir, manifest, session_factory=session_factory
    )


def _upsert_job_from_manifest(
    db: Session | None,
    workdir: Path,
    manifest: dict[str, Any],
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> None:
    payload = _manifest_db_payload(workdir, manifest)
    if db is not None:
        AiwikiJobDAO(db).upsert_from_payload(payload)
        return

    factory = session_factory or SessionLocal
    session = factory()
    try:
        AiwikiJobDAO(session).upsert_from_payload(payload)
    except Exception as exc:
        logger.warning("同步 AI Wiki 任务到数据库失败 {}: {}", manifest.get("id"), exc)
    finally:
        session.close()


def _build_session_factory(db: Session) -> sessionmaker[Session]:
    bind = db.get_bind()
    if isinstance(bind, Connection):
        bind = bind.engine
    if not isinstance(bind, Engine):
        raise RuntimeError("无法创建 AI Wiki 任务会话工厂")
    return sessionmaker(bind=bind, autocommit=False, autoflush=False)


def _manifest_db_payload(workdir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": manifest.get("id") or workdir.name,
        "status": manifest.get("status") or "queued",
        "message": manifest.get("message"),
        "workdir": manifest.get("workdir") or workdir.as_posix(),
        "raw_date": manifest.get("raw_date"),
        "files": manifest.get("files") or [],
        "summary": manifest.get("summary"),
        "created_at": manifest.get("created_at"),
        "started_at": manifest.get("started_at"),
        "finished_at": manifest.get("finished_at"),
    }


def _recover_interrupted_manifest(
    workdir: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    recovered = dict(manifest)
    if _progress_marked_complete(workdir):
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


def _append_log(workdir: Path, line: str) -> None:
    log_path = workdir / "logs" / "opencode.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(line.rstrip() + "\n")


def _read_log_tail(workdir: Path) -> list[str]:
    log_path = workdir / "logs" / "opencode.log"
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-LOG_TAIL_LINES:]


def _parse_json_list(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _parse_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_uploaded_files(value: str | None) -> list[UploadedFileOut]:
    return [
        UploadedFileOut.model_validate(item)
        for item in _parse_json_list(value)
        if isinstance(item, dict)
    ]


def _coerce_job_status(value: str) -> JobStatus:
    if value not in {"queued", "running", "completed", "failed"}:
        return "failed"
    return cast(JobStatus, value)


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[\x00-\x1f/\\:]+", "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:160] or "upload.txt"
