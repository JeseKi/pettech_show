# -*- coding: utf-8 -*-
"""Request-level Personal AI Wiki service functions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.server.aiwiki.parser import parse_aiwiki_result
from src.server.aiwiki.parser.wiki import split_frontmatter
from src.server.auth.models import User

from ..dao import PersonalAiwikiJobDAO
from ..schemas import (
    PersonalAiwikiEntryPageOut,
    PersonalAiwikiJobListOut,
    PersonalAiwikiJobOut,
    PersonalAiwikiJobUpdate,
    PersonalAiwikiOperation,
    PersonalAiwikiResultOut,
)
from .access import get_accessible_job
from .persistence import manifest_db_payload, read_manifest, write_manifest
from .queue import get_queue
from .runner import build_session_factory, run_job
from .serializers import (
    build_result_from_job,
    build_stats,
    job_out_from_model,
    job_summary_from_model,
    normalize_optional_text,
    parse_json_list,
)
from .uploads import build_manifest, validate_uploads, write_text_source, write_uploads
from .workspace import (
    ensure_workspace,
    new_job_id,
    resolve_wiki_page_path,
    user_job_dir,
    user_workspace_root,
)


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

    validated_files = await validate_uploads(uploaded_files)
    now = datetime.now(timezone.utc)
    owner_id = int(current_user.id)
    job_id = new_job_id(now)
    workspace_root = user_workspace_root(owner_id)
    workdir = user_job_dir(owner_id, job_id)
    raw_date = now.strftime("%y%m%d")
    ensure_workspace(workspace_root)
    saved_files = write_uploads(
        workdir,
        workspace_root=workspace_root,
        raw_date=raw_date,
        job_id=job_id,
        files=validated_files,
    )
    if operation == "ingest" and normalized_text:
        saved_files.append(
            write_text_source(
                workdir,
                workspace_root=workspace_root,
                raw_date=raw_date,
                job_id=job_id,
                text=normalized_text,
                title=title,
            )
        )

    manifest = build_manifest(
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
    from src.server.aiwiki.service.progress import initial_progress, write_progress

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
    import shutil

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
