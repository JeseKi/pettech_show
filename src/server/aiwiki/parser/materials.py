# -*- coding: utf-8 -*-
"""Parse AI Wiki material JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schemas import MaterialOut
from .utils import relative, string


def parse_materials(workdir: Path) -> list[MaterialOut]:
    material_root = workdir / "material"
    if not material_root.exists():
        return []

    materials: list[MaterialOut] = []
    for path in sorted(material_root.glob("*/*.json"), key=lambda item: item.as_posix()):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        metadata = data.get("元数据") if isinstance(data.get("元数据"), dict) else {}
        title = string(metadata.get("标题")) or path.stem
        source_path = relative(path, workdir)
        materials.append(
            MaterialOut(
                path=source_path,
                title=title,
                positioning=string(data.get("文章定位")),
                pain_points=normalize_asset_list(data.get("痛点"), "痛点"),
                hotspots=normalize_asset_list(data.get("蹭到的热点"), "热点"),
                solutions=normalize_asset_list(data.get("解决方案"), "方案"),
                topics=[item for item in data.get("选题", []) if isinstance(item, str)],
                search_intents=normalize_search_intents(data.get("搜索入口"), source_path),
                summary=data.get("总结") if isinstance(data.get("总结"), dict) else {},
            )
        )
    return materials


def normalize_asset_list(value: Any, key_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append({"title": item.strip(), "description": ""})
        elif isinstance(item, dict):
            title = (
                string(item.get(key_name))
                or string(item.get("标题"))
                or string(item.get("方案"))
                or string(item.get("热点"))
                or string(item.get("痛点"))
            )
            if title:
                normalized.append(
                    {
                        "title": title,
                        "description": string(item.get("说明"))
                        or string(item.get("对应内容"))
                        or string(item.get("描述"))
                        or "",
                        "raw": item,
                    }
                )
    return normalized


def normalize_search_intents(value: Any, source_material: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        keyword = string(item.get("关键词"))
        if not keyword:
            continue
        normalized = dict(item)
        normalized["source_material"] = source_material
        items.append(normalized)
    return items
