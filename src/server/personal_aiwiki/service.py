# -*- coding: utf-8 -*-
"""Personal AI Wiki service."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, cast

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from loguru import logger
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.parser import parse_aiwiki_result
from src.server.aiwiki.parser.wiki import split_frontmatter
from src.server.aiwiki.queue import AiwikiJobQueue
from src.server.aiwiki.schemas import JobStatus, UploadedFileOut
from src.server.aiwiki.service.constants import ALLOWED_EXTENSIONS
from src.server.aiwiki.service.files import (
    build_file_preview,
    category_for_extension,
    convert_to_markdown,
    default_mime_type,
    safe_filename,
)
from src.server.aiwiki.service.logs import append_log, read_log_tail
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.progress import (
    initial_progress,
    mark_progress_failure,
    progress_marked_complete,
    read_progress,
    write_progress,
)
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config
from src.server.database import SessionLocal
from src.server.opencode import run_opencode_in_tmux

from .dao import PersonalAiwikiJobDAO
from .models import PersonalAiwikiJob
from .schemas import (
    PersonalAiwikiJobListOut,
    PersonalAiwikiJobOut,
    PersonalAiwikiJobSummaryOut,
    PersonalAiwikiJobUpdate,
    PersonalAiwikiOperation,
    PersonalAiwikiEntryPageOut,
    PersonalAiwikiResultOut,
    PersonalAiwikiStatsOut,
)

_QUEUE: AiwikiJobQueue | None = None
_WORKSPACE_LOCKS: dict[int, Lock] = {}
_WORKSPACE_LOCKS_GUARD = Lock()


def reset_queue_for_tests() -> None:
    global _QUEUE
    if _QUEUE is not None:
        _QUEUE.shutdown()
    _QUEUE = None


def get_queue() -> AiwikiJobQueue:
    global _QUEUE
    if _QUEUE is None:
        _QUEUE = AiwikiJobQueue(max_workers=global_config.aiwiki_max_concurrent)
    return _QUEUE


async def create_job(
    db: Session,
    *,
    files: list[UploadFile] | None,
    current_user: User,
    operation: PersonalAiwikiOperation,
    input_text: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> PersonalAiwikiJobOut:
    normalized_text = normalize_optional_text(input_text)
    if operation != "ingest":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="个人 AI Wiki 任务目前只支持整理资料")
    uploaded_files = files or []
    if operation == "ingest" and not uploaded_files and not normalized_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传文件或填写要沉淀的资料")

    validated_files = await _validate_uploads(uploaded_files)
    now = datetime.now(timezone.utc)
    owner_id = int(current_user.id)
    job_id = new_job_id(now)
    workspace_root = user_workspace_root(owner_id)
    workdir = user_job_dir(owner_id, job_id)
    raw_date = now.strftime("%y%m%d")
    ensure_workspace(workspace_root)
    saved_files = _write_uploads(
        workdir,
        workspace_root=workspace_root,
        raw_date=raw_date,
        job_id=job_id,
        files=validated_files,
    )
    if operation == "ingest" and normalized_text:
        saved_files.append(
            _write_text_source(
                workdir,
                workspace_root=workspace_root,
                raw_date=raw_date,
                job_id=job_id,
                text=normalized_text,
                title=title,
            )
        )

    manifest = _build_manifest(
        job_id=job_id,
        owner_user_id=owner_id,
        operation=operation,
        workdir=workdir,
        workspace_root=workspace_root,
        input_text=normalized_text,
        title=normalize_optional_text(title),
        description=normalize_optional_text(description),
        files=saved_files,
        created_at=now,
        raw_date=raw_date,
    )
    write_progress(workdir, initial_progress())
    write_manifest(workdir, manifest)
    job = PersonalAiwikiJobDAO(db).upsert_from_payload(manifest_db_payload(manifest))
    session_factory = build_session_factory(db)
    get_queue().enqueue(job_id, lambda: run_job(job_id, workdir, session_factory))
    return job_out_from_model(job, queue_position=get_queue().queue_position(job_id))


def list_jobs(
    db: Session,
    *,
    limit: int,
    offset: int,
    current_user: User,
    status: str | None = None,
    operation: str | None = None,
) -> PersonalAiwikiJobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    owner_filter = current_user.id
    normalized_operation = operation if operation in {"ingest", "query", "lint"} else None
    dao = PersonalAiwikiJobDAO(db)
    jobs = dao.list(
        limit=normalized_limit,
        offset=normalized_offset,
        owner_user_id=owner_filter,
        status=status,
        operation=normalized_operation,
    )
    all_jobs = dao.list(limit=1000, offset=0, owner_user_id=owner_filter)
    return PersonalAiwikiJobListOut(
        items=[job_summary_from_model(job, dao.owner_username(job.owner_user_id)) for job in jobs],
        total=dao.count(owner_user_id=owner_filter, status=status, operation=normalized_operation),
        limit=normalized_limit,
        offset=normalized_offset,
        stats=build_stats(all_jobs),
    )


def get_job(db: Session, job_id: str, current_user: User) -> PersonalAiwikiJobOut:
    job = get_accessible_job(db, job_id, current_user)
    return job_out_from_model(
        job,
        owner_username=PersonalAiwikiJobDAO(db).owner_username(job.owner_user_id),
        queue_position=get_queue().queue_position(job.id),
    )


def update_job(
    db: Session,
    job_id: str,
    payload: PersonalAiwikiJobUpdate,
    current_user: User,
) -> PersonalAiwikiJobOut:
    job = get_accessible_job(db, job_id, current_user)
    fields = payload.model_dump(exclude_unset=True)
    manifest = read_manifest(Path(job.workdir))
    if "title" in fields:
        manifest["title"] = normalize_optional_text(fields.get("title"))
    if "description" in fields:
        manifest["description"] = normalize_optional_text(fields.get("description"))
    write_manifest(Path(job.workdir), manifest)
    updated = PersonalAiwikiJobDAO(db).upsert_from_payload(manifest_db_payload(manifest))
    return job_out_from_model(
        updated,
        owner_username=PersonalAiwikiJobDAO(db).owner_username(updated.owner_user_id),
    )


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    job = get_accessible_job(db, job_id, current_user)
    if job.status in {"queued", "running"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务正在执行，完成或失败后才能删除")
    PersonalAiwikiJobDAO(db).delete(job)
    shutil.rmtree(job.workdir, ignore_errors=True)


def get_result(
    db: Session,
    job_id: str,
    current_user: User,
) -> PersonalAiwikiResultOut:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    return build_result_from_job(job)


def get_workspace(db: Session, current_user: User) -> PersonalAiwikiResultOut:
    workspace_root = user_workspace_root(int(current_user.id))
    ensure_workspace(workspace_root)
    result = parse_aiwiki_result(f"personal-aiwiki-user-{current_user.id}", workspace_root)
    return PersonalAiwikiResultOut.model_validate(
        {
            **result.model_dump(),
            "operation": None,
            "answer_markdown": None,
            "workspace_dir": workspace_root.as_posix(),
        }
    )


def get_entry_page(
    current_user: User,
    page: str,
) -> PersonalAiwikiEntryPageOut:
    workspace_root = user_workspace_root(int(current_user.id))
    ensure_workspace(workspace_root)
    wiki_root = (workspace_root / "wiki").resolve()
    path = resolve_wiki_page_path(wiki_root, page)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="词条不存在")

    markdown = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(markdown)
    title = str(frontmatter.get("title") or path.stem).strip() or path.stem
    entry_type = str(frontmatter.get("type") or path.parent.name).strip() or "wiki"
    return PersonalAiwikiEntryPageOut(
        slug=path.with_suffix("").relative_to(wiki_root).as_posix(),
        path=path.relative_to(workspace_root).as_posix(),
        title=title,
        type=entry_type,
        frontmatter=frontmatter,
        body_markdown=body,
        markdown=markdown,
    )


def get_file(
    db: Session,
    job_id: str,
    file_index: int,
    current_user: User,
) -> FileResponse:
    job = get_accessible_job(db, job_id, current_user)
    files = parse_json_list(job.files_json)
    if file_index < 0 or file_index >= len(files) or not isinstance(files[file_index], dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    file_info = files[file_index]
    upload_path = file_info.get("upload_path")
    if not isinstance(upload_path, str) or not upload_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    workdir = Path(job.workdir).resolve()
    path = (workdir / upload_path).resolve()
    try:
        path.relative_to(workdir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件路径非法") from exc
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return FileResponse(
        path,
        media_type=str(file_info.get("mime_type") or "application/octet-stream"),
        filename=str(file_info.get("filename") or path.name),
    )


def sync_job_records(db: Session) -> None:
    data_root = personal_aiwiki_root()
    if not data_root.exists():
        return
    dao = PersonalAiwikiJobDAO(db)
    for manifest_path in sorted(data_root.glob("users/user_*/jobs/*_personal_aiwiki/manifest.json")):
        try:
            manifest = read_manifest(manifest_path.parent)
        except Exception as exc:
            logger.warning("跳过无法读取的个人 AI Wiki manifest {}: {}", manifest_path, exc)
            continue
        if manifest.get("status") in {"queued", "running"}:
            manifest["status"] = "failed"
            manifest["message"] = "任务因服务重启中断，请重新提交"
            manifest["finished_at"] = manifest.get("finished_at") or datetime.now(timezone.utc).isoformat()
            write_manifest(manifest_path.parent, manifest)
        dao.upsert_from_payload(manifest_db_payload(manifest))


def run_job(
    job_id: str,
    workdir: Path,
    session_factory: sessionmaker[Session],
) -> None:
    manifest = read_manifest(workdir)
    owner_user_id = int(manifest["owner_user_id"])
    started_at = datetime.now(timezone.utc)
    update_manifest(
        workdir,
        status="running",
        message="正在整理个人知识库",
        started_at=started_at.isoformat(),
        session_factory=session_factory,
    )
    try:
        with workspace_lock(owner_user_id):
            prepare_skill(workdir)
            prepare_opencode_config(workdir)
            run_personal_aiwiki_opencode(workdir)
            if not progress_marked_complete(workdir):
                raise RuntimeError("progress.json 未写入任务完成标记")
            updated = read_manifest(workdir)
            result = parse_aiwiki_result(job_id, Path(updated["workspace_dir"]))
            answer = read_answer(workdir)
            update_manifest(
                workdir,
                status="completed",
                message="个人知识库已更新",
                finished_at=datetime.now(timezone.utc).isoformat(),
                summary=result.summary,
                answer_markdown=answer,
                session_factory=session_factory,
            )
    except Exception as exc:
        logger.exception("Personal AI Wiki job failed: {}", job_id)
        append_log(workdir, f"ERROR: {exc}")
        mark_progress_failure(workdir, str(exc))
        update_manifest(
            workdir,
            status="failed",
            message=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
            session_factory=session_factory,
        )


def run_personal_aiwiki_opencode(workdir: Path) -> None:
    manifest = read_manifest(workdir)
    prompt = build_prompt(
        workdir=workdir,
        workspace_root=Path(str(manifest["workspace_dir"])),
        operation=cast(PersonalAiwikiOperation, manifest["operation"]),
        input_text=manifest.get("input_text"),
        files=parse_json_list(manifest.get("files")),
    )
    run_opencode_in_tmux(
        workdir,
        title="Personal AI Wiki",
        prompt=prompt,
        opencode_dir=workdir.parent.parent,
    )


def build_prompt(
    *,
    workdir: Path,
    workspace_root: Path,
    operation: PersonalAiwikiOperation,
    input_text: Any,
    files: list[dict[str, Any]],
) -> str:
    wiki_path = workspace_root / "wiki"
    file_lines = "\n".join(
        f"- {item.get('filename')}：{item.get('raw_path')}"
        + (
            f"；已复制到个人 workspace：{item.get('workspace_raw_path')}"
            if item.get("workspace_raw_path")
            else ""
        )
        for item in files
    ) or "- 无上传文件"
    operation_goal = """导入资料：读取本次上传/输入的 raw markdown，并把可复用事实、实体、概念、关系、比较、问题沉淀进个人 Wiki。不要复制全文；保留 raw 原文不改。"""
    question_block = str(input_text).strip() if input_text else "无"
    return f"""
你在个人 AI Wiki 任务目录中工作：{workdir.as_posix()}

个人 Wiki workspace：{workspace_root.as_posix()}
WIKI_PATH：{wiki_path.as_posix()}

请严格只读写：
- 当前任务目录：{workdir.as_posix()}
- 当前用户个人 workspace：{workspace_root.as_posix()}
不得访问或修改其他项目目录、其他用户目录或系统目录。

必须使用当前任务目录内的 Skill：$llm-wiki。

进度协议：
- 当前任务目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件，禁止清空或重建已有 events。
- `event` 只能使用 `开始`、`完成` 或 `失败`；`event`、`step`、`summary` 必须使用中文。
- 每开始一个步骤，立刻重写 `progress.json`，追加 `开始` 事件，并把 `status` 设为 `running`。
- 每完成一个步骤，立刻重写 `progress.json`，追加 `完成` 事件。
- 如果任务失败，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 所有工作完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

任务类型：ingest
目标：
{operation_goal}

本次资料：
{file_lines}

用户输入：
{question_block}

输出要求：
- Wiki 内容必须写入 `{wiki_path.as_posix()}` 下；raw 原文保留在 `{(workspace_root / 'raw').as_posix()}`。
- 如果缺少 `SCHEMA.md`、`index.md`、`log.md` 或核心目录，先按 $llm-wiki 初始化。
- 每个新增或更新的词条必须有 YAML frontmatter，至少包含 title、type、created/updated、tags。
- 所有新词条必须能从 `wiki/index.md` 或其它词条通过 wikilink 到达。
- 每次导入后都要更新 `wiki/index.md` 和 `wiki/log.md`。
- 如果有摘要，也可以写入当前任务目录 `answer.md`。
- 完成后直接结束，不要等待用户继续输入。
""".strip()


async def _validate_uploads(files: list[UploadFile]) -> list[dict[str, Any]]:
    total_size = 0
    validated_files: list[dict[str, Any]] = []
    max_bytes = global_config.aiwiki_max_upload_mb * 1024 * 1024
    for index, file in enumerate(files, start=1):
        original_name = safe_filename(file.filename or f"upload-{index}.txt")
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的文件类型：{extension or original_name}")
        content = await file.read()
        total_size += len(content)
        if total_size > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"上传总大小不能超过 {global_config.aiwiki_max_upload_mb}MB")
        validated_files.append(
            {
                "filename": original_name,
                "extension": extension,
                "content": content,
                "content_type": file.content_type,
            }
        )
    return validated_files


def _write_uploads(
    workdir: Path,
    *,
    workspace_root: Path,
    raw_date: str,
    job_id: str,
    files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not files:
        (workdir / "logs").mkdir(parents=True, exist_ok=True)
        return []
    uploads_dir = workdir / "uploads"
    raw_dir = workdir / "raw" / raw_date
    workspace_raw_dir = workspace_root / "raw" / raw_date
    (workdir / "logs").mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    workspace_raw_dir.mkdir(parents=True, exist_ok=True)
    saved_files: list[dict[str, Any]] = []
    for index, item in enumerate(files, start=1):
        saved_files.append(
            _write_one_upload(
                workdir,
                workspace_root=workspace_root,
                uploads_dir=uploads_dir,
                raw_dir=raw_dir,
                workspace_raw_dir=workspace_raw_dir,
                raw_date=raw_date,
                job_id=job_id,
                index=index,
                item=item,
            )
        )
    return saved_files


def _write_one_upload(
    workdir: Path,
    *,
    workspace_root: Path,
    uploads_dir: Path,
    raw_dir: Path,
    workspace_raw_dir: Path,
    raw_date: str,
    job_id: str,
    index: int,
    item: dict[str, Any],
) -> dict[str, Any]:
    original_name = str(item["filename"])
    extension = str(item["extension"])
    content = item["content"]
    upload_path = uploads_dir / original_name
    upload_path.write_bytes(content)
    raw_text = convert_to_markdown(upload_path, content, extension)
    raw_base = safe_filename(f"{raw_date}_{index}_{Path(original_name).stem}")
    raw_path = raw_dir / f"{raw_base}.md"
    raw_path.write_text(raw_text, encoding="utf-8")
    workspace_raw_path = workspace_raw_dir / f"{job_id}_{index}_{Path(original_name).stem}.md"
    workspace_raw_path.write_text(raw_text, encoding="utf-8")
    preview = build_file_preview(original_name, content, extension)
    file_record = {
        "filename": original_name,
        "size_bytes": len(content),
        "upload_path": upload_path.relative_to(workdir).as_posix(),
        "raw_path": raw_path.relative_to(workdir).as_posix(),
        "workspace_raw_path": workspace_raw_path.relative_to(workspace_root).as_posix(),
        "extension": extension,
        "mime_type": item["content_type"] or default_mime_type(extension),
        "category": category_for_extension(extension),
        "preview_status": "ready",
        "preview": preview,
    }
    if extension == ".pdf":
        raw_source_path = raw_dir / f"{raw_base}.pdf"
        raw_source_path.write_bytes(content)
        file_record["raw_source_path"] = raw_source_path.relative_to(workdir).as_posix()
    return file_record


def _write_text_source(
    workdir: Path,
    *,
    workspace_root: Path,
    raw_date: str,
    job_id: str,
    text: str,
    title: str | None,
) -> dict[str, Any]:
    input_dir = workdir / "inputs"
    raw_dir = workdir / "raw" / raw_date
    workspace_raw_dir = workspace_root / "raw" / raw_date
    input_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    workspace_raw_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(f"{title or '输入文本'}.md")
    content = text.strip() + "\n"
    upload_path = input_dir / filename
    upload_path.write_text(content, encoding="utf-8")
    raw_base = safe_filename(f"{raw_date}_text_{Path(filename).stem}")
    raw_path = raw_dir / f"{raw_base}.md"
    raw_path.write_text(content, encoding="utf-8")
    workspace_raw_path = workspace_raw_dir / f"{job_id}_text_{Path(filename).stem}.md"
    workspace_raw_path.write_text(content, encoding="utf-8")
    return {
        "filename": filename,
        "size_bytes": len(content.encode("utf-8")),
        "upload_path": upload_path.relative_to(workdir).as_posix(),
        "raw_path": raw_path.relative_to(workdir).as_posix(),
        "workspace_raw_path": workspace_raw_path.relative_to(workspace_root).as_posix(),
        "extension": ".md",
        "mime_type": "text/markdown",
        "category": "graphic_text",
        "preview_status": "ready",
        "preview": {
            "kind": "text",
            "format": "markdown",
            "text": content[:200_000],
            "truncated": len(content) > 200_000,
            "character_count": len(content),
        },
    }


def _build_manifest(
    *,
    job_id: str,
    owner_user_id: int,
    operation: PersonalAiwikiOperation,
    workdir: Path,
    workspace_root: Path,
    input_text: str | None,
    title: str | None,
    description: str | None,
    files: list[dict[str, Any]],
    created_at: datetime,
    raw_date: str,
) -> dict[str, Any]:
    return {
        "id": job_id,
        "owner_user_id": owner_user_id,
        "operation": operation,
        "title": title or default_job_title(operation, files, input_text, job_id),
        "description": description,
        "status": "queued",
        "message": "任务已进入队列",
        "created_at": created_at.isoformat(),
        "started_at": None,
        "finished_at": None,
        "workdir": workdir.as_posix(),
        "workspace_dir": workspace_root.as_posix(),
        "input_text": input_text,
        "files": files,
        "raw_date": raw_date,
        "summary": None,
        "answer_markdown": None,
    }


def default_job_title(
    operation: PersonalAiwikiOperation,
    files: list[dict[str, Any]],
    input_text: str | None,
    fallback_id: str,
) -> str:
    first_file = files[0].get("filename") if files else None
    if isinstance(first_file, str) and first_file.strip():
        return f"{first_file.strip()} 等 {len(files)} 个来源" if len(files) > 1 else first_file.strip()
    first_line = (input_text or "").strip().splitlines()[0:1]
    return (first_line[0][:80] if first_line else "") or fallback_id


def job_out_from_model(
    job: PersonalAiwikiJob,
    owner_username: str | None = None,
    queue_position: int | None = None,
) -> PersonalAiwikiJobOut:
    return PersonalAiwikiJobOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        operation=coerce_operation(job.operation),
        title=job.title or job.id,
        description=job.description,
        status=coerce_job_status(job.status),
        queue_position=queue_position,
        message=job.message,
        workspace_dir=job.workspace_dir,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        files=parse_uploaded_files(job.files_json),
        progress=read_progress(Path(job.workdir)),
        log_tail=read_log_tail(Path(job.workdir)),
    )


def job_summary_from_model(
    job: PersonalAiwikiJob,
    owner_username: str | None = None,
) -> PersonalAiwikiJobSummaryOut:
    return PersonalAiwikiJobSummaryOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        operation=coerce_operation(job.operation),
        title=job.title or job.id,
        description=job.description,
        status=coerce_job_status(job.status),
        message=job.message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        files=parse_uploaded_files(job.files_json),
        summary=parse_json_dict(job.summary_json),
    )


def build_result_from_job(job: PersonalAiwikiJob) -> PersonalAiwikiResultOut:
    result = parse_aiwiki_result(job.id, Path(job.workspace_dir))
    return PersonalAiwikiResultOut.model_validate(
        {
            **result.model_dump(),
            "operation": coerce_operation(job.operation),
            "answer_markdown": job.answer_markdown,
            "workspace_dir": job.workspace_dir,
        }
    )


def build_stats(jobs: list[PersonalAiwikiJob]) -> PersonalAiwikiStatsOut:
    return PersonalAiwikiStatsOut(
        ingest_count=sum(1 for job in jobs if job.operation == "ingest"),
        query_count=sum(1 for job in jobs if job.operation == "query"),
        lint_count=sum(1 for job in jobs if job.operation == "lint"),
        active_count=sum(1 for job in jobs if job.status in {"queued", "running"}),
        completed_count=sum(1 for job in jobs if job.status == "completed"),
        total_count=len(jobs),
    )


def get_accessible_job(db: Session, job_id: str, current_user: User) -> PersonalAiwikiJob:
    if not re.fullmatch(r"\d{14}_[a-f0-9]{8}_personal_aiwiki", job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    job = PersonalAiwikiJobDAO(db).get(job_id)
    if job is None or not can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if not (Path(job.workdir) / "manifest.json").exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


def can_access_job(user: User, owner_user_id: int | None) -> bool:
    return owner_user_id == user.id or is_admin(user)


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def new_job_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_personal_aiwiki"


def personal_aiwiki_root() -> Path:
    return Path(global_config.project_root) / "data" / "personal_aiwiki"


def user_root(owner_user_id: int) -> Path:
    return personal_aiwiki_root() / "users" / f"user_{owner_user_id}"


def user_workspace_root(owner_user_id: int) -> Path:
    return user_root(owner_user_id) / "workspace"


def user_job_dir(owner_user_id: int, job_id: str) -> Path:
    return user_root(owner_user_id) / "jobs" / job_id


def ensure_workspace(workspace_root: Path) -> None:
    wiki_root = workspace_root / "wiki"
    for folder in (
        workspace_root / "raw",
        wiki_root / "entities",
        wiki_root / "concepts",
        wiki_root / "comparisons",
        wiki_root / "queries",
    ):
        folder.mkdir(parents=True, exist_ok=True)
    schema_path = wiki_root / "SCHEMA.md"
    index_path = wiki_root / "index.md"
    log_path = wiki_root / "log.md"
    today = datetime.now(timezone.utc).date().isoformat()
    if not schema_path.exists():
        schema_path.write_text(DEFAULT_SCHEMA, encoding="utf-8")
    if not index_path.exists():
        index_path.write_text(
            f"---\ntitle: 个人知识库\ntype: index\ncreated: {today}\nupdated: {today}\ntags: [personal-ai-wiki]\n---\n\n# 个人知识库\n\n## 最近更新\n\n- 暂无整理内容。\n\n## 入口\n\n- [[queries/index|问答索引]]\n",
            encoding="utf-8",
        )
    query_index_path = wiki_root / "queries" / "index.md"
    if not query_index_path.exists():
        query_index_path.write_text(
            f"---\ntitle: 问答索引\ntype: query\ncreated: {today}\nupdated: {today}\ntags: [personal-ai-wiki]\n---\n\n# 问答索引\n\n暂无沉淀问答。\n",
            encoding="utf-8",
        )
    if not log_path.exists():
        log_path.write_text(f"# 个人 AI Wiki 日志\n\n- {today} 初始化个人 Wiki。\n", encoding="utf-8")


def resolve_wiki_page_path(wiki_root: Path, page: str) -> Path:
    normalized = normalize_wiki_page(page)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供词条路径")
    if normalized.startswith("/") or normalized.startswith("\\"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="词条路径非法")

    candidate = wiki_root / normalized
    if candidate.suffix.lower() != ".md":
        candidate = candidate.with_suffix(".md")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(wiki_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="词条路径非法") from exc
    return resolved


def normalize_wiki_page(page: str) -> str:
    text = page.strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    if "|" in text:
        text = text.split("|", 1)[0].strip()
    if "#" in text:
        text = text.split("#", 1)[0].strip()
    text = text.removeprefix("wiki/").removeprefix("./")
    return text


DEFAULT_SCHEMA = """# 个人 AI Wiki Schema

所有 Wiki 内容位于 `wiki/` 下，原始资料位于同级 `raw/` 下。原始资料只追加、不改写。

## 目录

- `index.md`：个人 Wiki 首页和主要入口。
- `log.md`：按时间记录导入和重要修订。
- `SCHEMA.md`：本文件，记录结构约定。
- `entities/`：人物、组织、产品、项目、地点等实体。
- `concepts/`：概念、方法、原则、事实卡。
- `comparisons/`：对比、权衡、决策记录。
- `queries/`：有长期价值的问题、答案和检索路径。

## 词条 frontmatter

```yaml
---
title: 词条标题
type: entity | concept | comparison | query | note | index
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [标签]
sources:
  - raw/260626/example.md
---
```

## 链接规范

- 使用 `[[folder/slug]]` 或 `[[folder/slug|展示文本]]` 连接相关词条。
- 新词条必须能从 `index.md` 或已有词条追溯到。
- 不确定的信息必须标注来源和置信度，不要写成定论。
"""


def workspace_lock(owner_user_id: int) -> Lock:
    with _WORKSPACE_LOCKS_GUARD:
        lock = _WORKSPACE_LOCKS.get(owner_user_id)
        if lock is None:
            lock = Lock()
            _WORKSPACE_LOCKS[owner_user_id] = lock
        return lock


def prepare_skill(workdir: Path) -> None:
    source = Path(__file__).resolve().parent / "skills" / "llm-wiki"
    target_root = workdir / ".agents" / "skills"
    target = target_root / "llm-wiki"
    target_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def build_session_factory(db: Session) -> sessionmaker[Session]:
    bind = db.get_bind()
    if isinstance(bind, Connection):
        bind = bind.engine
    if not isinstance(bind, Engine):
        raise RuntimeError("无法创建个人 AI Wiki 任务会话工厂")
    return sessionmaker(bind=bind, autocommit=False, autoflush=False)


def read_manifest(workdir: Path) -> dict[str, Any]:
    return json.loads((workdir / "manifest.json").read_text(encoding="utf-8"))


def write_manifest(workdir: Path, manifest: dict[str, Any]) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / "manifest.json"
    tmp_path = workdir / f"manifest.json.{secrets.token_hex(8)}.tmp"
    tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def update_manifest(
    workdir: Path,
    *,
    session_factory: sessionmaker[Session] | None = None,
    **fields: Any,
) -> None:
    manifest = read_manifest(workdir)
    manifest.update(fields)
    write_manifest(workdir, manifest)
    upsert_job_from_manifest(manifest, session_factory=session_factory)


def upsert_job_from_manifest(
    manifest: dict[str, Any],
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> PersonalAiwikiJob | None:
    factory = session_factory or SessionLocal
    session = factory()
    try:
        return PersonalAiwikiJobDAO(session).upsert_from_payload(manifest_db_payload(manifest))
    except Exception as exc:
        logger.warning("同步个人 AI Wiki 任务到数据库失败 {}: {}", manifest.get("id"), exc)
        return None
    finally:
        session.close()


def manifest_db_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": manifest.get("id"),
        "owner_user_id": manifest.get("owner_user_id"),
        "status": manifest.get("status") or "queued",
        "operation": manifest.get("operation") or "ingest",
        "title": manifest.get("title"),
        "description": manifest.get("description"),
        "message": manifest.get("message"),
        "workdir": manifest.get("workdir"),
        "workspace_dir": manifest.get("workspace_dir"),
        "input_text": manifest.get("input_text"),
        "files": manifest.get("files") or [],
        "summary": manifest.get("summary"),
        "answer_markdown": manifest.get("answer_markdown"),
        "created_at": manifest.get("created_at"),
        "started_at": manifest.get("started_at"),
        "finished_at": manifest.get("finished_at"),
    }


def read_answer(workdir: Path) -> str | None:
    answer_path = workdir / "answer.md"
    if not answer_path.exists():
        return None
    answer = answer_path.read_text(encoding="utf-8", errors="replace").strip()
    return answer or None


def parse_json_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def parse_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_uploaded_files(value: str | None) -> list[UploadedFileOut]:
    return [UploadedFileOut.model_validate(item) for item in parse_json_list(value)]


def coerce_job_status(value: str) -> JobStatus:
    if value not in {"queued", "running", "completed", "failed"}:
        return "failed"
    return cast(JobStatus, value)


def coerce_operation(value: str) -> PersonalAiwikiOperation:
    if value in {"ingest", "query", "lint"}:
        return cast(PersonalAiwikiOperation, value)
    return "ingest"


def normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
