# -*- coding: utf-8 -*-
"""Interactive movie editing services."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.config import global_config

from .models import (
    InteractiveMovieChoice,
    InteractiveMovieProject,
    InteractiveMovieScene,
    InteractiveMovieScriptLine,
    InteractiveMovieViewport,
    utc_now,
)
from .schemas import (
    InteractiveMovieProjectCreateIn,
    InteractiveMovieProjectPatchIn,
    InteractiveMovieProjectRenameIn,
    UploadedVideoOut,
)


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


def list_projects(db: Session, user: User) -> list[dict[str, Any]]:
    projects = (
        db.query(InteractiveMovieProject)
        .filter(InteractiveMovieProject.owner_user_id == user.id)
        .order_by(InteractiveMovieProject.updated_at.desc(), InteractiveMovieProject.created_at.desc())
        .all()
    )
    summaries: list[dict[str, Any]] = []
    for project in projects:
        scene_count = db.query(InteractiveMovieScene).filter(InteractiveMovieScene.project_id == project.id).count()
        choice_count = db.query(InteractiveMovieChoice).filter(InteractiveMovieChoice.project_id == project.id).count()
        summaries.append({
            "id": project.id,
            "title": project.title,
            "version": project.version,
            "content_hash": project.content_hash,
            "updated_at": _iso(project.updated_at),
            "scene_count": scene_count,
            "choice_count": choice_count,
        })
    return summaries


def create_project(db: Session, user: User, payload: InteractiveMovieProjectCreateIn) -> dict[str, Any]:
    document = payload.document
    existing = db.query(InteractiveMovieProject).filter(InteractiveMovieProject.id == document.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="项目 ID 已存在")

    now = utc_now()
    snapshot = _normalize_document(document.model_dump())
    content_hash = compute_content_hash(snapshot)
    selected = snapshot.get("selectedObject") or {}
    project = InteractiveMovieProject(
        id=document.id,
        owner_user_id=user.id,
        title=payload.title.strip() or document.title,
        canvas_json=json.dumps(snapshot, ensure_ascii=False),
        version=1,
        content_hash=content_hash,
        selected_object_type=str(selected.get("type") or "scene"),
        selected_object_id=str(selected.get("id") or ""),
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    _replace_project_children(db, project.id, snapshot)
    db.commit()
    return get_project(db, user, project.id)


def get_project(db: Session, user: User, project_id: str) -> dict[str, Any]:
    project = _get_owned_project(db, user, project_id)
    return _project_out(db, project)


def get_sync_state(db: Session, user: User, project_id: str) -> dict[str, Any]:
    project = _get_owned_project(db, user, project_id)
    return {
        "project_id": project.id,
        "version": project.version,
        "content_hash": project.content_hash,
        "updated_at": _iso(project.updated_at),
    }


def patch_project(db: Session, user: User, project_id: str, payload: InteractiveMovieProjectPatchIn) -> dict[str, Any]:
    project = _get_owned_project(db, user, project_id)
    if project.version != payload.base_version or project.content_hash != payload.base_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "version_conflict",
                "remote_version": project.version,
                "remote_hash": project.content_hash,
            },
        )

    _apply_patch(db, project, payload)
    snapshot = _snapshot(db, project)
    project.content_hash = compute_content_hash(snapshot)
    project.canvas_json = json.dumps(snapshot, ensure_ascii=False)
    project.version += 1
    project.updated_at = utc_now()
    db.commit()
    db.refresh(project)
    return _project_out(db, project)


def rename_project(db: Session, user: User, project_id: str, payload: InteractiveMovieProjectRenameIn) -> dict[str, Any]:
    project = _get_owned_project(db, user, project_id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目名称不能为空")

    project.title = title[:200]
    project.version += 1
    project.updated_at = utc_now()
    snapshot = _snapshot(db, project)
    project.content_hash = compute_content_hash(snapshot)
    project.canvas_json = json.dumps(snapshot, ensure_ascii=False)
    db.commit()
    db.refresh(project)
    return _project_out(db, project)


def delete_project(db: Session, user: User, project_id: str) -> None:
    project = _get_owned_project(db, user, project_id)
    _delete_project_children(db, project.id)
    db.delete(project)
    db.commit()


def compute_content_hash(document: dict[str, Any]) -> str:
    payload = json.dumps(_canonical_document(document), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def prompt_template() -> dict[str, Any]:
    """Return a structured prompt helper for future video generation."""
    return {
        "sections": [
            "主体：谁或什么是画面核心，保持描述具体。",
            "动作：主体正在做什么，单镜头只保留一组主要动作。",
            "场景：空间、时代、天气、道具、情绪氛围。",
            "镜头：景别、机位、运镜或镜头切换方式。",
            "时序：按秒描述关键动作变化，例如 [0-2s] / [2-5s]。",
            "风格：写实、动画、电影质感、色彩、光线、材质。",
            "约束：不要出现的内容、主体一致性、字幕/水印限制。",
        ],
        "example": (
            "主体：年轻女性林夏站在老式公寓走廊。\n"
            "动作：[0-2s] 她低头看见门口湿掉的信封；[2-5s] 她缓慢蹲下捡起信，神情迟疑。\n"
            "场景：雨夜，狭窄老公寓走廊，暖黄色灯光闪烁，地面潮湿。\n"
            "镜头：电影级中景缓慢推近，浅景深，轻微手持感。\n"
            "风格：悬疑短片，写实，低饱和，高对比，环境声紧张。\n"
            "约束：不出现文字水印，不切换主角，不夸张恐怖。"
        ),
    }


async def read_video_upload(file: UploadFile) -> bytes:
    content_type = file.content_type or ""
    extension = Path(file.filename or "").suffix.lower()
    if not content_type.startswith("video/") and extension not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持上传视频文件",
        )

    max_bytes = global_config.interactive_movie_max_video_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"视频不能超过 {global_config.interactive_movie_max_video_upload_mb}MB",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空")
    return content


def upload_video(file: UploadFile, content: bytes) -> UploadedVideoOut:
    config = _s3_config()
    filename = _safe_filename(file.filename or "scene-video.mp4")
    content_type = file.content_type or "application/octet-stream"
    object_key = _object_key(filename)
    full_key = _full_key(config["prefix"], object_key)

    try:
        _s3_client(config).put_object(
            Bucket=config["bucket"],
            Key=full_key,
            Body=content,
            ContentType=content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"S3 上传失败：{exc}") from exc

    return UploadedVideoOut(
        url=_access_url(config, full_key),
        storage_uri=f"s3://{config['bucket']}/{full_key}",
        object_key=object_key,
        filename=filename,
        content_type=content_type,
        size=len(content),
    )


def _s3_config() -> dict[str, str]:
    config = {
        "endpoint_url": global_config.interactive_movie_s3_endpoint_url.strip(),
        "region_name": global_config.interactive_movie_s3_region_name.strip(),
        "bucket": global_config.interactive_movie_s3_bucket.strip(),
        "access_key_id": global_config.interactive_movie_s3_access_key_id.strip(),
        "secret_access_key": global_config.interactive_movie_s3_secret_access_key.strip(),
        "prefix": global_config.interactive_movie_s3_prefix.strip(),
        "public_base_url": global_config.interactive_movie_s3_public_base_url.strip(),
    }
    missing = [
        name
        for name in ("endpoint_url", "bucket", "access_key_id", "secret_access_key")
        if not config[name]
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"互动电影 S3 配置缺失：{', '.join(missing)}",
        )
    return config


def _s3_client(config: dict[str, str]) -> Any:
    try:
        import boto3  # type: ignore[import-not-found, import-untyped]
    except ImportError as exc:
        raise RuntimeError("S3 上传需要安装 boto3") from exc

    return boto3.client(
        "s3",
        endpoint_url=config["endpoint_url"],
        region_name=config["region_name"] or None,
        aws_access_key_id=config["access_key_id"],
        aws_secret_access_key=config["secret_access_key"],
    )


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip().replace("\\", "_").replace("/", "_")
    return name[:160] or "scene-video.mp4"


def _object_key(filename: str) -> str:
    now = datetime.now(timezone.utc)
    extension = Path(filename).suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        extension = ".mp4"
    return f"videos/{now:%Y/%m/%d}/{uuid4().hex}{extension}"


def _full_key(prefix: str, object_key: str) -> str:
    normalized_prefix = prefix.strip("/")
    return f"{normalized_prefix}/{object_key}" if normalized_prefix else object_key


def _access_url(config: dict[str, str], full_key: str) -> str | None:
    if config["public_base_url"]:
        return f"{config['public_base_url'].rstrip('/')}/{quote(full_key, safe='/')}"

    try:
        return _s3_client(config).generate_presigned_url(
            "get_object",
            Params={"Bucket": config["bucket"], "Key": full_key},
            ExpiresIn=global_config.interactive_movie_s3_presign_expires_seconds,
        )
    except Exception:
        return None


def _get_owned_project(db: Session, user: User, project_id: str) -> InteractiveMovieProject:
    project = (
        db.query(InteractiveMovieProject)
        .populate_existing()
        .filter(
            InteractiveMovieProject.id == project_id,
            InteractiveMovieProject.owner_user_id == user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="互动电影项目不存在")
    return project


def _replace_project_children(db: Session, project_id: str, document: dict[str, Any]) -> None:
    _delete_project_children(db, project_id)
    viewport = document.get("viewport") or {}
    db.add(InteractiveMovieViewport(
        project_id=project_id,
        x=float(viewport.get("x") or 0),
        y=float(viewport.get("y") or 0),
        zoom=float(viewport.get("zoom") or 1),
    ))
    for index, scene in enumerate(document.get("scenes") or []):
        db.add(_scene_from_dict(project_id, scene, index))
        for line_index, line in enumerate((scene.get("script") or {}).get("lines") or []):
            db.add(_line_from_dict(scene["id"], line, line_index))
    for index, choice in enumerate(document.get("choices") or []):
        db.add(_choice_from_dict(project_id, choice, index))


def _delete_project_children(db: Session, project_id: str) -> None:
    scene_ids = [row[0] for row in db.query(InteractiveMovieScene.id).filter(InteractiveMovieScene.project_id == project_id).all()]
    if scene_ids:
        db.query(InteractiveMovieScriptLine).filter(InteractiveMovieScriptLine.scene_id.in_(scene_ids)).delete(synchronize_session=False)
    db.query(InteractiveMovieChoice).filter(InteractiveMovieChoice.project_id == project_id).delete(synchronize_session=False)
    db.query(InteractiveMovieScene).filter(InteractiveMovieScene.project_id == project_id).delete(synchronize_session=False)
    db.query(InteractiveMovieViewport).filter(InteractiveMovieViewport.project_id == project_id).delete(synchronize_session=False)


def _apply_patch(db: Session, project: InteractiveMovieProject, payload: InteractiveMovieProjectPatchIn) -> None:
    now = utc_now()
    if "title" in payload.project:
        project.title = str(payload.project["title"])[:200]
    if payload.selected_object:
        project.selected_object_type = str(payload.selected_object.get("type") or project.selected_object_type)
        project.selected_object_id = str(payload.selected_object.get("id") or project.selected_object_id)
    if payload.viewport:
        viewport = db.query(InteractiveMovieViewport).filter(InteractiveMovieViewport.project_id == project.id).first()
        if not viewport:
            viewport = InteractiveMovieViewport(project_id=project.id, x=0, y=0, zoom=1)
            db.add(viewport)
        for key in ("x", "y", "zoom"):
            if key in payload.viewport:
                setattr(viewport, key, float(payload.viewport[key]))

    for scene_id in payload.scenes.delete:
        db.query(InteractiveMovieScriptLine).filter(InteractiveMovieScriptLine.scene_id == scene_id).delete(synchronize_session=False)
        db.query(InteractiveMovieChoice).filter(
            (InteractiveMovieChoice.from_scene_id == scene_id) | (InteractiveMovieChoice.to_scene_id == scene_id)
        ).delete(synchronize_session=False)
        db.query(InteractiveMovieScene).filter(
            InteractiveMovieScene.project_id == project.id,
            InteractiveMovieScene.id == scene_id,
        ).delete(synchronize_session=False)

    for choice_id in payload.choices.delete:
        db.query(InteractiveMovieChoice).filter(
            InteractiveMovieChoice.project_id == project.id,
            InteractiveMovieChoice.id == choice_id,
        ).delete(synchronize_session=False)

    for line_id in payload.script_lines.delete:
        db.query(InteractiveMovieScriptLine).filter(InteractiveMovieScriptLine.id == line_id).delete(synchronize_session=False)

    for index, scene_patch in enumerate(payload.scenes.upsert):
        scene_id = str(scene_patch.get("id") or "")
        if not scene_id:
            continue
        scene = db.query(InteractiveMovieScene).filter(InteractiveMovieScene.id == scene_id, InteractiveMovieScene.project_id == project.id).first()
        if not scene:
            scene = _scene_from_dict(project.id, _scene_patch_to_full(scene_patch), index)
            db.add(scene)
        _update_scene_from_patch(scene, scene_patch, now)

    for index, line_patch in enumerate(payload.script_lines.upsert):
        line_id = str(line_patch.get("id") or "")
        scene_id = str(line_patch.get("sceneId") or line_patch.get("scene_id") or "")
        if not line_id or not scene_id:
            continue
        line = db.query(InteractiveMovieScriptLine).filter(InteractiveMovieScriptLine.id == line_id).first()
        if not line:
            line = InteractiveMovieScriptLine(id=line_id, scene_id=scene_id, speaker="", text="", sort_order=index)
            db.add(line)
        if "sceneId" in line_patch or "scene_id" in line_patch:
            line.scene_id = scene_id
        if "speaker" in line_patch:
            line.speaker = str(line_patch["speaker"])
        if "text" in line_patch:
            line.text = str(line_patch["text"])
        if "sortOrder" in line_patch:
            line.sort_order = int(line_patch["sortOrder"])

    for index, choice_patch in enumerate(payload.choices.upsert):
        choice_id = str(choice_patch.get("id") or "")
        if not choice_id:
            continue
        choice = db.query(InteractiveMovieChoice).filter(InteractiveMovieChoice.id == choice_id, InteractiveMovieChoice.project_id == project.id).first()
        if not choice:
            choice = _choice_from_dict(project.id, _choice_patch_to_full(choice_patch), index)
            db.add(choice)
        _update_choice_from_patch(choice, choice_patch)


def _scene_from_dict(project_id: str, scene: dict[str, Any], sort_order: int) -> InteractiveMovieScene:
    script = scene.get("script") or {}
    prompt = script.get("promptParts") or {}
    position = scene.get("position") or {}
    media = scene.get("media") or {}
    return InteractiveMovieScene(
        id=str(scene["id"]),
        project_id=project_id,
        title=str(scene.get("title") or "未命名场景"),
        role=str(scene.get("role") or "middle"),
        position_x=float(position.get("x") or 0),
        position_y=float(position.get("y") or 0),
        synopsis=str(script.get("synopsis") or ""),
        visual_description=str(script.get("visualDescription") or ""),
        video_prompt=str(script.get("videoPrompt") or ""),
        prompt_subject=str(prompt.get("subject") or ""),
        prompt_action=str(prompt.get("action") or ""),
        prompt_scene=str(prompt.get("scene") or ""),
        prompt_camera=str(prompt.get("camera") or ""),
        prompt_timeline=str(prompt.get("timeline") or ""),
        prompt_style=str(prompt.get("style") or ""),
        prompt_constraints=str(prompt.get("constraints") or ""),
        media_kind=str(media.get("kind") or "placeholder"),
        media_url=str(media.get("url") or ""),
        media_object_key=str(media.get("objectKey") or ""),
        media_storage_uri=str(media.get("storageUri") or ""),
        poster_url=str(media.get("posterUrl") or ""),
        media_status=str(media.get("status") or "mock"),
        sort_order=sort_order,
        updated_at=utc_now(),
    )


def _line_from_dict(scene_id: str, line: dict[str, Any], sort_order: int) -> InteractiveMovieScriptLine:
    return InteractiveMovieScriptLine(
        id=str(line["id"]),
        scene_id=scene_id,
        speaker=str(line.get("speaker") or ""),
        text=str(line.get("text") or ""),
        sort_order=sort_order,
    )


def _choice_from_dict(project_id: str, choice: dict[str, Any], sort_order: int) -> InteractiveMovieChoice:
    return InteractiveMovieChoice(
        id=str(choice["id"]),
        project_id=project_id,
        from_scene_id=str(choice.get("fromSceneId") or ""),
        to_scene_id=str(choice.get("toSceneId") or ""),
        label=str(choice.get("label") or "新的选择"),
        trigger=str(choice.get("trigger") or "after_scene"),
        offset_y=float(choice.get("offsetY") or 0),
        sort_order=sort_order,
    )


def _update_scene_from_patch(scene: InteractiveMovieScene, patch: dict[str, Any], now: datetime) -> None:
    mapping = {
        "title": "title",
        "role": "role",
        "synopsis": "synopsis",
        "visualDescription": "visual_description",
        "videoPrompt": "video_prompt",
        "promptSubject": "prompt_subject",
        "promptAction": "prompt_action",
        "promptScene": "prompt_scene",
        "promptCamera": "prompt_camera",
        "promptTimeline": "prompt_timeline",
        "promptStyle": "prompt_style",
        "promptConstraints": "prompt_constraints",
        "mediaKind": "media_kind",
        "mediaUrl": "media_url",
        "mediaObjectKey": "media_object_key",
        "mediaStorageUri": "media_storage_uri",
        "posterUrl": "poster_url",
        "mediaStatus": "media_status",
    }
    for src, dest in mapping.items():
        if src in patch:
            setattr(scene, dest, str(patch[src] or ""))
    if "positionX" in patch:
        scene.position_x = float(patch["positionX"])
    if "positionY" in patch:
        scene.position_y = float(patch["positionY"])
    if "sortOrder" in patch:
        scene.sort_order = int(patch["sortOrder"])
    scene.updated_at = now


def _update_choice_from_patch(choice: InteractiveMovieChoice, patch: dict[str, Any]) -> None:
    if "fromSceneId" in patch:
        choice.from_scene_id = str(patch["fromSceneId"])
    if "toSceneId" in patch:
        choice.to_scene_id = str(patch["toSceneId"])
    if "label" in patch:
        choice.label = str(patch["label"])
    if "trigger" in patch:
        choice.trigger = str(patch["trigger"])
    if "offsetY" in patch:
        choice.offset_y = float(patch["offsetY"])
    if "sortOrder" in patch:
        choice.sort_order = int(patch["sortOrder"])


def _snapshot(db: Session, project: InteractiveMovieProject) -> dict[str, Any]:
    scenes = (
        db.query(InteractiveMovieScene)
        .filter(InteractiveMovieScene.project_id == project.id)
        .order_by(InteractiveMovieScene.sort_order.asc(), InteractiveMovieScene.id.asc())
        .all()
    )
    choices = (
        db.query(InteractiveMovieChoice)
        .filter(InteractiveMovieChoice.project_id == project.id)
        .order_by(InteractiveMovieChoice.sort_order.asc(), InteractiveMovieChoice.id.asc())
        .all()
    )
    viewport = db.query(InteractiveMovieViewport).filter(InteractiveMovieViewport.project_id == project.id).first()
    scene_docs = []
    for scene in scenes:
        lines = (
            db.query(InteractiveMovieScriptLine)
            .filter(InteractiveMovieScriptLine.scene_id == scene.id)
            .order_by(InteractiveMovieScriptLine.sort_order.asc(), InteractiveMovieScriptLine.id.asc())
            .all()
        )
        scene_docs.append({
            "id": scene.id,
            "title": scene.title,
            "role": scene.role,
            "position": {"x": scene.position_x, "y": scene.position_y},
            "media": {
                "kind": scene.media_kind,
                "url": scene.media_url,
                "objectKey": scene.media_object_key,
                "storageUri": scene.media_storage_uri,
                "posterUrl": scene.poster_url,
                "status": scene.media_status,
            },
            "script": {
                "synopsis": scene.synopsis,
                "visualDescription": scene.visual_description,
                "videoPrompt": scene.video_prompt,
                "promptParts": {
                    "subject": scene.prompt_subject,
                    "action": scene.prompt_action,
                    "scene": scene.prompt_scene,
                    "camera": scene.prompt_camera,
                    "timeline": scene.prompt_timeline,
                    "style": scene.prompt_style,
                    "constraints": scene.prompt_constraints,
                },
                "lines": [{"id": line.id, "speaker": line.speaker, "text": line.text} for line in lines],
            },
        })
    return {
        "id": project.id,
        "title": project.title,
        "updatedAt": _iso(project.updated_at),
        "scenes": scene_docs,
        "choices": [
            {
                "id": choice.id,
                "fromSceneId": choice.from_scene_id,
                "toSceneId": choice.to_scene_id,
                "label": choice.label,
                "trigger": choice.trigger,
                "offsetY": choice.offset_y,
            }
            for choice in choices
        ],
        "selectedObject": {
            "type": project.selected_object_type,
            "id": project.selected_object_id,
        },
        "viewport": {
            "x": viewport.x if viewport else 360,
            "y": viewport.y if viewport else 160,
            "zoom": viewport.zoom if viewport else 1,
        },
    }


def _project_out(db: Session, project: InteractiveMovieProject) -> dict[str, Any]:
    return {
        "id": project.id,
        "title": project.title,
        "version": project.version,
        "content_hash": project.content_hash,
        "updated_at": _iso(project.updated_at),
        "document": _snapshot(db, project),
    }


def _normalize_document(document: dict[str, Any]) -> dict[str, Any]:
    if not document.get("selectedObject"):
        first_scene = (document.get("scenes") or [{}])[0]
        document["selectedObject"] = {"type": "scene", "id": first_scene.get("id", "")}
    return document


def _canonical_document(document: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(document)
    cleaned.pop("updatedAt", None)
    cleaned["scenes"] = sorted(cleaned.get("scenes") or [], key=lambda item: item.get("id", ""))
    cleaned["choices"] = sorted(cleaned.get("choices") or [], key=lambda item: item.get("id", ""))
    for scene in cleaned["scenes"]:
        script = scene.get("script") or {}
        script["lines"] = sorted(script.get("lines") or [], key=lambda item: item.get("id", ""))
    return cleaned


def _scene_patch_to_full(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch["id"],
        "title": patch.get("title") or "未命名场景",
        "role": patch.get("role") or "middle",
        "position": {"x": patch.get("positionX") or 0, "y": patch.get("positionY") or 0},
        "media": {},
        "script": {},
    }


def _choice_patch_to_full(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch["id"],
        "fromSceneId": patch.get("fromSceneId") or "",
        "toSceneId": patch.get("toSceneId") or "",
        "label": patch.get("label") or "新的选择",
        "trigger": patch.get("trigger") or "after_scene",
        "offsetY": patch.get("offsetY") or 0,
    }


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
