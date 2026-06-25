# -*- coding: utf-8 -*-
"""Update helpers for interactive movie persistence."""

from __future__ import annotations

from typing import Any

from ..models import InteractiveMovieChoice


def update_choice_from_patch(choice: InteractiveMovieChoice, patch: dict[str, Any]) -> None:
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


def scene_patch_to_full(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch["id"],
        "title": patch.get("title") or "未命名场景",
        "role": patch.get("role") or "middle",
        "position": {"x": patch.get("positionX") or 0, "y": patch.get("positionY") or 0},
        "media": {},
        "script": {},
    }


def choice_patch_to_full(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch["id"],
        "fromSceneId": patch.get("fromSceneId") or "",
        "toSceneId": patch.get("toSceneId") or "",
        "label": patch.get("label") or "新的选择",
        "trigger": patch.get("trigger") or "after_scene",
        "offsetY": patch.get("offsetY") or 0,
    }
