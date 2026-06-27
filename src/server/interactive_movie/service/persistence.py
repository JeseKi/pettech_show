# -*- coding: utf-8 -*-
"""Persistence helpers for interactive movie document rows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    InteractiveMovieAssetNode,
    InteractiveMovieChoice,
    InteractiveMovieNodeLink,
    InteractiveMovieProject,
    InteractiveMovieScene,
    InteractiveMovieScriptLine,
    InteractiveMovieViewport,
    utc_now,
)
from ..schemas import InteractiveMovieProjectPatchIn
from .persistence_updates import (
    asset_patch_to_full,
    choice_patch_to_full,
    node_link_patch_to_full,
    update_asset_node_from_patch,
    scene_patch_to_full,
    update_choice_from_patch,
    update_node_link_from_patch,
)


def replace_project_children(db: Session, project_id: str, document: dict[str, Any]) -> None:
    delete_project_children(db, project_id)
    viewport = document.get("viewport") or {}
    db.add(InteractiveMovieViewport(
        project_id=project_id,
        x=float(viewport.get("x") or 0),
        y=float(viewport.get("y") or 0),
        zoom=float(viewport.get("zoom") or 1),
    ))
    for index, scene in enumerate(document.get("scenes") or []):
        db.add(scene_from_dict(project_id, scene, index))
        for line_index, line in enumerate((scene.get("script") or {}).get("lines") or []):
            db.add(line_from_dict(scene["id"], line, line_index))
    for index, choice in enumerate(document.get("choices") or []):
        db.add(choice_from_dict(project_id, choice, index))
    for index, asset in enumerate(document.get("assetNodes") or []):
        db.add(asset_node_from_dict(project_id, asset, index))
    for index, link in enumerate(document.get("nodeLinks") or []):
        db.add(node_link_from_dict(project_id, link, index))


def delete_project_children(db: Session, project_id: str) -> None:
    scene_ids = [
        row[0]
        for row in db.query(InteractiveMovieScene.id)
        .filter(InteractiveMovieScene.project_id == project_id)
        .all()
    ]
    if scene_ids:
        db.query(InteractiveMovieScriptLine).filter(
            InteractiveMovieScriptLine.scene_id.in_(scene_ids)
        ).delete(synchronize_session=False)
    db.query(InteractiveMovieChoice).filter(
        InteractiveMovieChoice.project_id == project_id
    ).delete(synchronize_session=False)
    db.query(InteractiveMovieAssetNode).filter(
        InteractiveMovieAssetNode.project_id == project_id
    ).delete(synchronize_session=False)
    db.query(InteractiveMovieNodeLink).filter(
        InteractiveMovieNodeLink.project_id == project_id
    ).delete(synchronize_session=False)
    db.query(InteractiveMovieScene).filter(
        InteractiveMovieScene.project_id == project_id
    ).delete(synchronize_session=False)
    db.query(InteractiveMovieViewport).filter(
        InteractiveMovieViewport.project_id == project_id
    ).delete(synchronize_session=False)


def apply_patch(db: Session, project: InteractiveMovieProject, payload: InteractiveMovieProjectPatchIn) -> None:
    now = utc_now()
    if "title" in payload.project:
        project.title = str(payload.project["title"])[:200]
    if payload.selected_object:
        project.selected_object_type = str(payload.selected_object.get("type") or project.selected_object_type)
        project.selected_object_id = str(payload.selected_object.get("id") or project.selected_object_id)
    if payload.viewport:
        _upsert_viewport(db, project, payload.viewport)

    for scene_id in payload.scenes.delete:
        db.query(InteractiveMovieScriptLine).filter(
            InteractiveMovieScriptLine.scene_id == scene_id
        ).delete(synchronize_session=False)
        db.query(InteractiveMovieChoice).filter(
            (InteractiveMovieChoice.from_scene_id == scene_id) | (InteractiveMovieChoice.to_scene_id == scene_id)
        ).delete(synchronize_session=False)
        db.query(InteractiveMovieNodeLink).filter(
            (
                (InteractiveMovieNodeLink.from_node_type == "scene")
                & (InteractiveMovieNodeLink.from_node_id == scene_id)
            )
            | (
                (InteractiveMovieNodeLink.to_node_type == "scene")
                & (InteractiveMovieNodeLink.to_node_id == scene_id)
            )
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

    asset_patch = getattr(payload, "asset_nodes", None)
    if asset_patch:
        for asset_id in asset_patch.delete:
            db.query(InteractiveMovieNodeLink).filter(
                (
                    (InteractiveMovieNodeLink.from_node_id == asset_id)
                    & (InteractiveMovieNodeLink.from_node_type.in_(("text", "image", "video")))
                )
                | (
                    (InteractiveMovieNodeLink.to_node_id == asset_id)
                    & (InteractiveMovieNodeLink.to_node_type.in_(("text", "image", "video")))
                )
            ).delete(synchronize_session=False)
            db.query(InteractiveMovieAssetNode).filter(
                InteractiveMovieAssetNode.project_id == project.id,
                InteractiveMovieAssetNode.id == asset_id,
            ).delete(synchronize_session=False)

    link_patch = getattr(payload, "node_links", None)
    if link_patch:
        for link_id in link_patch.delete:
            db.query(InteractiveMovieNodeLink).filter(
                InteractiveMovieNodeLink.project_id == project.id,
                InteractiveMovieNodeLink.id == link_id,
            ).delete(synchronize_session=False)

    for line_id in payload.script_lines.delete:
        db.query(InteractiveMovieScriptLine).filter(
            InteractiveMovieScriptLine.id == line_id
        ).delete(synchronize_session=False)

    _upsert_scenes(db, project, payload, now)
    _upsert_asset_nodes(db, project, payload, now)
    _upsert_node_links(db, project, payload)
    _upsert_script_lines(db, payload)
    _upsert_choices(db, project, payload)


def scene_from_dict(project_id: str, scene: dict[str, Any], sort_order: int) -> InteractiveMovieScene:
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
        video_node_id=str(media.get("videoNodeId") or ""),
        cover_image_node_id=str(media.get("coverImageNodeId") or ""),
        media_status=str(media.get("status") or "mock"),
        sort_order=sort_order,
        updated_at=utc_now(),
    )


def asset_node_from_dict(project_id: str, asset: dict[str, Any], sort_order: int) -> InteractiveMovieAssetNode:
    position = asset.get("position") or {}
    media = asset.get("media") or {}
    return InteractiveMovieAssetNode(
        id=str(asset["id"]),
        project_id=project_id,
        type=str(asset.get("type") or "text"),
        title=str(asset.get("title") or "未命名素材"),
        position_x=float(position.get("x") or 0),
        position_y=float(position.get("y") or 0),
        text=str(asset.get("text") or ""),
        media_url=str(media.get("url") or ""),
        media_object_key=str(media.get("objectKey") or ""),
        media_storage_uri=str(media.get("storageUri") or ""),
        media_content_type=str(media.get("contentType") or ""),
        media_size=int(media.get("size") or 0),
        media_status=str(media.get("status") or "empty"),
        sort_order=sort_order,
        updated_at=utc_now(),
    )


def line_from_dict(scene_id: str, line: dict[str, Any], sort_order: int) -> InteractiveMovieScriptLine:
    return InteractiveMovieScriptLine(
        id=str(line["id"]),
        scene_id=scene_id,
        speaker=str(line.get("speaker") or ""),
        text=str(line.get("text") or ""),
        sort_order=sort_order,
    )


def choice_from_dict(project_id: str, choice: dict[str, Any], sort_order: int) -> InteractiveMovieChoice:
    return InteractiveMovieChoice(
        id=str(choice["id"]),
        project_id=project_id,
        from_scene_id=str(choice.get("fromSceneId") or ""),
        to_scene_id=str(choice.get("toSceneId") or ""),
        label=str(choice.get("label") or "新的选择"),
        trigger=str(choice.get("trigger") or "after_scene"),
        offset_x=float(choice.get("offsetX") or 0),
        offset_y=float(choice.get("offsetY") or 0),
        sort_order=sort_order,
    )


def node_link_from_dict(project_id: str, link: dict[str, Any], sort_order: int) -> InteractiveMovieNodeLink:
    source = link.get("from") or {}
    target = link.get("to") or {}
    return InteractiveMovieNodeLink(
        id=str(link["id"]),
        project_id=project_id,
        from_node_type=str(source.get("type") or "scene"),
        from_node_id=str(source.get("id") or ""),
        from_handle=str(source.get("handle") or "right"),
        to_node_type=str(target.get("type") or "scene"),
        to_node_id=str(target.get("id") or ""),
        to_handle=str(target.get("handle") or "left"),
        offset_x=float(link.get("offsetX") or 0),
        offset_y=float(link.get("offsetY") or 0),
        sort_order=sort_order,
    )


def _upsert_viewport(db: Session, project: InteractiveMovieProject, patch: dict[str, Any]) -> None:
    viewport = db.query(InteractiveMovieViewport).filter(InteractiveMovieViewport.project_id == project.id).first()
    if not viewport:
        viewport = InteractiveMovieViewport(project_id=project.id, x=0, y=0, zoom=1)
        db.add(viewport)
    for key in ("x", "y", "zoom"):
        if key in patch:
            setattr(viewport, key, float(patch[key]))


def _upsert_scenes(
    db: Session,
    project: InteractiveMovieProject,
    payload: InteractiveMovieProjectPatchIn,
    now: datetime,
) -> None:
    for index, scene_patch in enumerate(payload.scenes.upsert):
        scene_id = str(scene_patch.get("id") or "")
        if not scene_id:
            continue
        scene = db.query(InteractiveMovieScene).filter(
            InteractiveMovieScene.id == scene_id,
            InteractiveMovieScene.project_id == project.id,
        ).first()
        if not scene:
            scene = scene_from_dict(project.id, scene_patch_to_full(scene_patch), index)
            db.add(scene)
        _update_scene_from_patch(scene, scene_patch, now)


def _upsert_asset_nodes(
    db: Session,
    project: InteractiveMovieProject,
    payload: InteractiveMovieProjectPatchIn,
    now: datetime,
) -> None:
    asset_patch = getattr(payload, "asset_nodes", None)
    if not asset_patch:
        return
    for index, patch in enumerate(asset_patch.upsert):
        asset_id = str(patch.get("id") or "")
        if not asset_id:
            continue
        asset = db.query(InteractiveMovieAssetNode).filter(
            InteractiveMovieAssetNode.id == asset_id,
            InteractiveMovieAssetNode.project_id == project.id,
        ).first()
        if not asset:
            asset = asset_node_from_dict(project.id, asset_patch_to_full(patch), index)
            db.add(asset)
        update_asset_node_from_patch(asset, patch)
        asset.updated_at = now


def _upsert_script_lines(db: Session, payload: InteractiveMovieProjectPatchIn) -> None:
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


def _upsert_node_links(db: Session, project: InteractiveMovieProject, payload: InteractiveMovieProjectPatchIn) -> None:
    link_patch = getattr(payload, "node_links", None)
    if not link_patch:
        return
    for index, patch in enumerate(link_patch.upsert):
        link_id = str(patch.get("id") or "")
        if not link_id:
            continue
        link = db.query(InteractiveMovieNodeLink).filter(
            InteractiveMovieNodeLink.id == link_id,
            InteractiveMovieNodeLink.project_id == project.id,
        ).first()
        if not link:
            link = node_link_from_dict(project.id, node_link_patch_to_full(patch), index)
            db.add(link)
        update_node_link_from_patch(link, patch)


def _upsert_choices(db: Session, project: InteractiveMovieProject, payload: InteractiveMovieProjectPatchIn) -> None:
    for index, choice_patch in enumerate(payload.choices.upsert):
        choice_id = str(choice_patch.get("id") or "")
        if not choice_id:
            continue
        choice = db.query(InteractiveMovieChoice).filter(
            InteractiveMovieChoice.id == choice_id,
            InteractiveMovieChoice.project_id == project.id,
        ).first()
        if not choice:
            choice = choice_from_dict(project.id, choice_patch_to_full(choice_patch), index)
            db.add(choice)
        update_choice_from_patch(choice, choice_patch)


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
        "videoNodeId": "video_node_id",
        "coverImageNodeId": "cover_image_node_id",
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
