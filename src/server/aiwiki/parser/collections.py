# -*- coding: utf-8 -*-
"""Aggregate parsed AI Wiki assets for API output."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..schemas import MaterialOut, WikiEntryOut
from .utils import extract_terms, section_excerpt, string


def collect_search_intents(
    materials: list[MaterialOut], wiki_entries: list[WikiEntryOut]
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for material in materials:
        for item in material.search_intents:
            key = (string(item.get("关键词")), string(item.get("意图类型")))
            if key in seen:
                continue
            seen.add(key)
            collected.append(item)

    for entry in wiki_entries:
        if entry.type != "search_intent":
            continue
        collected.append(
            {
                "意图类型": "词条",
                "关键词": entry.title,
                "搜索意图": section_excerpt(entry),
                "source_wiki": entry.path,
            }
        )
    return collected


def collect_named_assets(
    materials: list[MaterialOut],
    wiki_entries: list[WikiEntryOut],
    entry_type: str,
    material_attr: str,
) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for material in materials:
        for item in getattr(material, material_attr):
            title = string(item.get("title"))
            if title and title not in seen:
                seen.add(title)
                assets.append({**item, "source_material": material.path})

    for entry in wiki_entries:
        if entry.type != entry_type or entry.title in seen:
            continue
        seen.add(entry.title)
        assets.append(
            {
                "title": entry.title,
                "description": section_excerpt(entry),
                "source_wiki": entry.path,
                "slug": entry.slug,
            }
        )
    return assets


def collect_topics(
    materials: list[MaterialOut], wiki_entries: list[WikiEntryOut]
) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    seen: set[str] = set()
    for material in materials:
        for topic in material.topics:
            if topic in seen:
                continue
            seen.add(topic)
            topics.append({"title": topic, "status": "idea", "source_material": material.path})

    for entry in wiki_entries:
        if entry.type != "topic" or entry.title in seen:
            continue
        seen.add(entry.title)
        topics.append(
            {
                "title": entry.title,
                "status": string(entry.frontmatter.get("status")) or "idea",
                "source_wiki": entry.path,
                "slug": entry.slug,
                "description": section_excerpt(entry),
            }
        )
    return topics


def collect_highlight_terms(
    materials: list[MaterialOut], wiki_entries: list[WikiEntryOut]
) -> list[str]:
    counter: Counter[str] = Counter()
    for material in materials:
        for item in material.search_intents:
            keyword = string(item.get("关键词"))
            if keyword:
                counter[keyword] += 4
        for topic in material.topics:
            for term in extract_terms(topic):
                counter[term] += 1

    for entry in wiki_entries:
        tags = entry.frontmatter.get("tags", [])
        for tag in tags if isinstance(tags, list) else []:
            if isinstance(tag, str):
                counter[tag] += 2
        for term in extract_terms(entry.title):
            counter[term] += 1

    return [term for term, _ in counter.most_common(80)]


def build_summary(
    materials: list[MaterialOut],
    wiki_entries: list[WikiEntryOut],
    search_intents: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "material_count": len(materials),
        "wiki_entry_count": len(wiki_entries),
        "search_intent_count": len(search_intents),
        "topic_count": sum(len(material.topics) for material in materials)
        + sum(1 for entry in wiki_entries if entry.type == "topic"),
    }


def build_navigation(
    wiki_entries: list[WikiEntryOut], materials: list[MaterialOut]
) -> list[dict[str, Any]]:
    groups = [
        ("overview", "概览", 1),
        ("entries", "词条预览", len(wiki_entries)),
        ("hotspot", "热点", sum(1 for item in wiki_entries if item.type == "hotspot")),
        (
            "pain_point",
            "痛点",
            sum(1 for item in wiki_entries if item.type == "pain_point"),
        ),
        ("solution", "解决方案", sum(1 for item in wiki_entries if item.type == "solution")),
        ("topic", "选题", sum(1 for item in wiki_entries if item.type == "topic")),
        (
            "search_intent",
            "搜索入口",
            sum(1 for item in wiki_entries if item.type == "search_intent"),
        ),
    ]
    return [{"key": key, "label": label, "count": count} for key, label, count in groups]
