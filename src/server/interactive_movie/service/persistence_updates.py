# -*- coding: utf-8 -*-
"""Update helpers for interactive movie persistence."""

from __future__ import annotations

from typing import Any

from ..models import InteractiveMovieAssetNode, InteractiveMovieChoice, InteractiveMovieNodeLink


def update_choice_from_patch(choice: InteractiveMovieChoice, patch: dict[str, Any]) -> None:
    if "fromSceneId" in patch:
        choice.from_scene_id = str(patch["fromSceneId"])
    if "toSceneId" in patch:
        choice.to_scene_id = str(patch["toSceneId"])
    if "label" in patch:
        choice.label = str(patch["label"])
    if "trigger" in patch:
        choice.trigger = str(patch["trigger"])
    if "offsetX" in patch:
        choice.offset_x = float(patch["offsetX"])
    if "offsetY" in patch:
        choice.offset_y = float(patch["offsetY"])
    if "sortOrder" in patch:
        choice.sort_order = int(patch["sortOrder"])


def update_asset_node_from_patch(asset: InteractiveMovieAssetNode, patch: dict[str, Any]) -> None:
    mapping = {
        "type": "type",
        "title": "title",
        "text": "text",
        "mediaUrl": "media_url",
        "mediaObjectKey": "media_object_key",
        "mediaStorageUri": "media_storage_uri",
        "mediaContentType": "media_content_type",
        "mediaStatus": "media_status",
    }
    for src, dest in mapping.items():
        if src in patch:
            setattr(asset, dest, str(patch[src] or ""))
    if "mediaSize" in patch:
        asset.media_size = int(patch["mediaSize"] or 0)
    if "positionX" in patch:
        asset.position_x = float(patch["positionX"])
    if "positionY" in patch:
        asset.position_y = float(patch["positionY"])
    if "sortOrder" in patch:
        asset.sort_order = int(patch["sortOrder"])


def update_node_link_from_patch(link: InteractiveMovieNodeLink, patch: dict[str, Any]) -> None:
    mapping = {
        "fromNodeType": "from_node_type",
        "fromNodeId": "from_node_id",
        "fromHandle": "from_handle",
        "toNodeType": "to_node_type",
        "toNodeId": "to_node_id",
        "toHandle": "to_handle",
    }
    for src, dest in mapping.items():
        if src in patch:
            setattr(link, dest, str(patch[src] or ""))
    if "offsetX" in patch:
        link.offset_x = float(patch["offsetX"])
    if "offsetY" in patch:
        link.offset_y = float(patch["offsetY"])
    if "sortOrder" in patch:
        link.sort_order = int(patch["sortOrder"])


def scene_patch_to_full(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch["id"],
        "title": patch.get("title") or "未命名场景",
        "role": patch.get("role") or "middle",
        "position": {"x": patch.get("positionX") or 0, "y": patch.get("positionY") or 0},
        "media": {},
        "script": {},
    }


def asset_patch_to_full(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch["id"],
        "type": patch.get("type") or "text",
        "title": patch.get("title") or "未命名素材",
        "position": {"x": patch.get("positionX") or 0, "y": patch.get("positionY") or 0},
        "text": patch.get("text") or "",
        "media": {
            "url": patch.get("mediaUrl") or "",
            "objectKey": patch.get("mediaObjectKey") or "",
            "storageUri": patch.get("mediaStorageUri") or "",
            "contentType": patch.get("mediaContentType") or "",
            "size": patch.get("mediaSize") or 0,
            "status": patch.get("mediaStatus") or "empty",
        },
    }


def choice_patch_to_full(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch["id"],
        "fromSceneId": patch.get("fromSceneId") or "",
        "toSceneId": patch.get("toSceneId") or "",
        "label": patch.get("label") or "新的选择",
        "trigger": patch.get("trigger") or "after_scene",
        "offsetX": patch.get("offsetX") or 0,
        "offsetY": patch.get("offsetY") or 0,
    }


def node_link_patch_to_full(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch["id"],
        "from": {
            "type": patch.get("fromNodeType") or "scene",
            "id": patch.get("fromNodeId") or "",
            "handle": patch.get("fromHandle") or "right",
        },
        "to": {
            "type": patch.get("toNodeType") or "scene",
            "id": patch.get("toNodeId") or "",
            "handle": patch.get("toHandle") or "left",
        },
        "offsetX": patch.get("offsetX") or 0,
        "offsetY": patch.get("offsetY") or 0,
    }
