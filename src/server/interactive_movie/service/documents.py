# -*- coding: utf-8 -*-
"""Document hashing and serialization helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import timezone
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
)
from .publication import publication_fields


def compute_content_hash(document: dict[str, Any]) -> str:
    payload = json.dumps(
        _canonical_document(document),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def normalize_document(document: dict[str, Any]) -> dict[str, Any]:
    if not document.get("selectedObject"):
        first_scene = (document.get("scenes") or [{}])[0]
        document["selectedObject"] = {"type": "scene", "id": first_scene.get("id", "")}
    return document


def snapshot(db: Session, project: InteractiveMovieProject) -> dict[str, Any]:
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
    asset_nodes = (
        db.query(InteractiveMovieAssetNode)
        .filter(InteractiveMovieAssetNode.project_id == project.id)
        .order_by(InteractiveMovieAssetNode.sort_order.asc(), InteractiveMovieAssetNode.id.asc())
        .all()
    )
    node_links = (
        db.query(InteractiveMovieNodeLink)
        .filter(InteractiveMovieNodeLink.project_id == project.id)
        .order_by(InteractiveMovieNodeLink.sort_order.asc(), InteractiveMovieNodeLink.id.asc())
        .all()
    )
    viewport = db.query(InteractiveMovieViewport).filter(InteractiveMovieViewport.project_id == project.id).first()
    scene_docs = [_scene_document(db, scene) for scene in scenes]
    return {
        "id": project.id,
        "title": project.title,
        "updatedAt": iso(project.updated_at),
        "scenes": scene_docs,
        "choices": [_choice_document(choice) for choice in choices],
        "assetNodes": [_asset_node_document(asset) for asset in asset_nodes],
        "nodeLinks": [_node_link_document(link) for link in node_links],
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


def project_out(db: Session, project: InteractiveMovieProject) -> dict[str, Any]:
    return {
        "id": project.id,
        "title": project.title,
        "version": project.version,
        "content_hash": project.content_hash,
        "updated_at": iso(project.updated_at),
        "document": snapshot(db, project),
        **publication_fields(db, project),
    }


def iso(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _scene_document(db: Session, scene: InteractiveMovieScene) -> dict[str, Any]:
    lines = (
        db.query(InteractiveMovieScriptLine)
        .filter(InteractiveMovieScriptLine.scene_id == scene.id)
        .order_by(InteractiveMovieScriptLine.sort_order.asc(), InteractiveMovieScriptLine.id.asc())
        .all()
    )
    return {
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
            "videoNodeId": scene.video_node_id,
            "coverImageNodeId": scene.cover_image_node_id,
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
    }


def _asset_node_document(asset: InteractiveMovieAssetNode) -> dict[str, Any]:
    return {
        "id": asset.id,
        "type": asset.type,
        "title": asset.title,
        "position": {"x": asset.position_x, "y": asset.position_y},
        "text": asset.text,
        "media": {
            "url": asset.media_url,
            "objectKey": asset.media_object_key,
            "storageUri": asset.media_storage_uri,
            "contentType": asset.media_content_type,
            "size": asset.media_size,
            "status": asset.media_status,
        },
    }


def _choice_document(choice: InteractiveMovieChoice) -> dict[str, Any]:
    return {
        "id": choice.id,
        "fromSceneId": choice.from_scene_id,
        "toSceneId": choice.to_scene_id,
        "label": choice.label,
        "trigger": choice.trigger,
        "offsetX": choice.offset_x,
        "offsetY": choice.offset_y,
    }


def _node_link_document(link: InteractiveMovieNodeLink) -> dict[str, Any]:
    return {
        "id": link.id,
        "from": {
            "type": link.from_node_type,
            "id": link.from_node_id,
            "handle": link.from_handle,
        },
        "to": {
            "type": link.to_node_type,
            "id": link.to_node_id,
            "handle": link.to_handle,
        },
        "offsetX": link.offset_x,
        "offsetY": link.offset_y,
    }


def _canonical_document(document: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(document)
    cleaned.pop("updatedAt", None)
    cleaned["scenes"] = sorted(cleaned.get("scenes") or [], key=lambda item: item.get("id", ""))
    cleaned["choices"] = sorted(cleaned.get("choices") or [], key=lambda item: item.get("id", ""))
    cleaned["assetNodes"] = sorted(cleaned.get("assetNodes") or [], key=lambda item: item.get("id", ""))
    cleaned["nodeLinks"] = sorted(cleaned.get("nodeLinks") or [], key=lambda item: item.get("id", ""))
    for scene in cleaned["scenes"]:
        script = scene.get("script") or {}
        script["lines"] = sorted(script.get("lines") or [], key=lambda item: item.get("id", ""))
    return cleaned
