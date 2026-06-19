# -*- coding: utf-8 -*-
"""Parse generated AI Wiki artifacts into display-oriented JSON."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .schemas import (
    AiwikiResultOut,
    MaterialOut,
    WikiEntryOut,
    WikiHomeOut,
    WikiReferenceOut,
)

WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def parse_aiwiki_result(job_id: str, workdir: Path) -> AiwikiResultOut:
    materials = _parse_materials(workdir)
    wiki_home = _parse_wiki_home(workdir)
    wiki_entries = _parse_wiki_entries(workdir)
    _attach_reference_links(wiki_entries)
    search_intents = _collect_search_intents(materials, wiki_entries)

    return AiwikiResultOut(
        job_id=job_id,
        summary=_build_summary(materials, wiki_entries, search_intents),
        materials=materials,
        hotspots=_collect_named_assets(materials, wiki_entries, "hotspot", "hotspots"),
        pain_points=_collect_named_assets(
            materials, wiki_entries, "pain_point", "pain_points"
        ),
        solutions=_collect_named_assets(materials, wiki_entries, "solution", "solutions"),
        topics=_collect_topics(materials, wiki_entries),
        search_intents=search_intents,
        wiki_home=wiki_home,
        wiki_entries=wiki_entries,
        highlight_terms=_collect_highlight_terms(materials, wiki_entries),
        navigation=_build_navigation(wiki_entries, materials),
    )


def _parse_materials(workdir: Path) -> list[MaterialOut]:
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
        title = _string(metadata.get("标题")) or path.stem
        materials.append(
            MaterialOut(
                path=_relative(path, workdir),
                title=title,
                positioning=_string(data.get("文章定位")),
                pain_points=_normalize_asset_list(data.get("痛点"), "痛点"),
                hotspots=_normalize_asset_list(data.get("蹭到的热点"), "热点"),
                solutions=_normalize_asset_list(data.get("解决方案"), "方案"),
                topics=[item for item in data.get("选题", []) if isinstance(item, str)],
                search_intents=_normalize_search_intents(
                    data.get("搜索入口"), _relative(path, workdir)
                ),
                summary=data.get("总结") if isinstance(data.get("总结"), dict) else {},
            )
        )
    return materials


def _parse_wiki_entries(workdir: Path) -> list[WikiEntryOut]:
    wiki_root = workdir / "wiki"
    if not wiki_root.exists():
        return []

    entries: list[WikiEntryOut] = []
    for path in sorted(wiki_root.glob("**/*.md"), key=lambda item: item.as_posix()):
        if path.name in {"index.md", "log.md"} or path.name.upper() == "SCHEMA.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = _split_frontmatter(text)
        title = _string(frontmatter.get("title")) or _first_heading(body) or path.stem
        rel = _relative(path, workdir)
        sections = _parse_sections(body)
        entries.append(
            WikiEntryOut(
                path=rel,
                slug=path.with_suffix("").relative_to(wiki_root).as_posix(),
                type=_entry_type(path, frontmatter, wiki_root),
                title=title,
                frontmatter=frontmatter,
                body_markdown=body,
                excerpt=_body_excerpt(body, sections),
                created=_string(frontmatter.get("created")) or None,
                updated=_string(frontmatter.get("updated")) or None,
                sections=sections,
                references=sorted(set(_extract_wikilinks(body))),
            )
        )
    return entries


def _parse_wiki_home(workdir: Path) -> WikiHomeOut | None:
    path = workdir / "wiki" / "index.md"
    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = _split_frontmatter(text)
    body = _clean_wiki_home_body(body)
    title = _string(frontmatter.get("title")) or _first_heading(body) or "AI Wiki"
    return WikiHomeOut(
        path=_relative(path, workdir),
        title=title,
        body_markdown=body,
        references=sorted(set(_extract_wikilinks(body))),
        headings=_extract_headings(body),
    )


def _attach_reference_links(entries: list[WikiEntryOut]) -> None:
    by_slug = {entry.slug: entry for entry in entries}
    for entry in entries:
        links: list[WikiReferenceOut] = []
        for slug in entry.references:
            target = by_slug.get(slug)
            links.append(
                WikiReferenceOut(
                    slug=slug,
                    title=target.title if target else slug,
                    path=target.path if target else None,
                    type=target.type if target else None,
                )
            )
        entry.reference_links = links


def _clean_wiki_home_body(body: str) -> str:
    cleaned_lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("> 素材来源"):
            continue
        if stripped == "## 选题（按状态分类）":
            cleaned_lines.append("## 选题")
            continue
        if re.match(r"^###\s+.+\((idea|draft|published|archived|done)\)\s*$", stripped):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip() + "\n"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    return _parse_simple_frontmatter(raw), body


def _parse_sections(body: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_title = "正文"
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections.append(
                    {"title": current_title, "content": "\n".join(current_lines).strip()}
                )
            current_title = line[3:].strip()
            current_lines = []
        elif not line.startswith("# "):
            current_lines.append(_render_wikilinks(line))
    if current_lines:
        sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})
    return [section for section in sections if section["content"]]


def _render_wikilinks(text: str) -> str:
    return WIKILINK_PATTERN.sub(lambda match: _wikilink_label(match.group(1)), text)


def _extract_wikilinks(text: str) -> list[str]:
    return [_wikilink_slug(match) for match in WIKILINK_PATTERN.findall(text)]


def _wikilink_slug(raw: str) -> str:
    return _split_wikilink(raw)[0]


def _wikilink_label(raw: str) -> str:
    slug, label = _split_wikilink(raw)
    return label or slug


def _split_wikilink(raw: str) -> tuple[str, str | None]:
    normalized = raw.replace("\\|", "|")
    if "|" not in normalized:
        return normalized.strip(), None
    slug, label = normalized.split("|", 1)
    return slug.strip(), label.strip() or None


def _parse_simple_frontmatter(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(stripped[2:].strip().strip('"\''))
            continue
        if ":" not in line:
            current_key = None
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        if not value:
            data[current_key] = []
        elif value.startswith("[") and value.endswith("]"):
            data[current_key] = [
                part.strip().strip("\"'")
                for part in value[1:-1].split(",")
                if part.strip()
            ]
        else:
            data[current_key] = value.strip('"\'')
    return data


def _normalize_asset_list(value: Any, key_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append({"title": item.strip(), "description": ""})
        elif isinstance(item, dict):
            title = (
                _string(item.get(key_name))
                or _string(item.get("标题"))
                or _string(item.get("方案"))
                or _string(item.get("热点"))
                or _string(item.get("痛点"))
            )
            if title:
                normalized.append(
                    {
                        "title": title,
                        "description": _string(item.get("说明"))
                        or _string(item.get("对应内容"))
                        or _string(item.get("描述"))
                        or "",
                        "raw": item,
                    }
                )
    return normalized


def _normalize_search_intents(value: Any, source_material: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        keyword = _string(item.get("关键词"))
        if not keyword:
            continue
        normalized = dict(item)
        normalized["source_material"] = source_material
        items.append(normalized)
    return items


def _collect_search_intents(
    materials: list[MaterialOut], wiki_entries: list[WikiEntryOut]
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for material in materials:
        for item in material.search_intents:
            key = (_string(item.get("关键词")), _string(item.get("意图类型")))
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
                "搜索意图": _section_excerpt(entry),
                "source_wiki": entry.path,
            }
        )
    return collected


def _collect_named_assets(
    materials: list[MaterialOut],
    wiki_entries: list[WikiEntryOut],
    entry_type: str,
    material_attr: str,
) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for material in materials:
        for item in getattr(material, material_attr):
            title = _string(item.get("title"))
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
                "description": _section_excerpt(entry),
                "source_wiki": entry.path,
                "slug": entry.slug,
            }
        )
    return assets


def _collect_topics(
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
                "status": _string(entry.frontmatter.get("status")) or "idea",
                "source_wiki": entry.path,
                "slug": entry.slug,
                "description": _section_excerpt(entry),
            }
        )
    return topics


def _collect_highlight_terms(
    materials: list[MaterialOut], wiki_entries: list[WikiEntryOut]
) -> list[str]:
    counter: Counter[str] = Counter()
    for material in materials:
        for item in material.search_intents:
            keyword = _string(item.get("关键词"))
            if keyword:
                counter[keyword] += 4
        for topic in material.topics:
            for term in _extract_terms(topic):
                counter[term] += 1

    for entry in wiki_entries:
        for tag in entry.frontmatter.get("tags", []) if isinstance(entry.frontmatter.get("tags"), list) else []:
            if isinstance(tag, str):
                counter[tag] += 2
        for term in _extract_terms(entry.title):
            counter[term] += 1

    return [term for term, _ in counter.most_common(80)]


def _build_summary(
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


def _build_navigation(
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


def _entry_type(path: Path, frontmatter: dict[str, Any], wiki_root: Path) -> str:
    explicit_type = _string(frontmatter.get("type"))
    if explicit_type:
        return explicit_type
    try:
        folder = path.relative_to(wiki_root).parts[0]
    except ValueError:
        return "wiki"
    return {
        "hotspots": "hotspot",
        "pain-points": "pain_point",
        "solutions": "solution",
        "topics": "topic",
        "search-intents": "search_intent",
        "articles": "article",
    }.get(folder, folder)


def _section_excerpt(entry: WikiEntryOut) -> str:
    for section in entry.sections:
        content = section.get("content", "").strip()
        if content:
            return content[:240]
    return ""


def _body_excerpt(body: str, sections: list[dict[str, str]]) -> str:
    for section in sections:
        content = section.get("content", "").strip()
        if content:
            return content[:240]
    stripped_lines = [
        _render_wikilinks(line).strip()
        for line in body.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return "\n".join(stripped_lines)[:240]


def _extract_headings(body: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for line in body.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if not match:
            continue
        headings.append(
            {
                "id": f"heading-{len(headings) + 1}",
                "level": len(match.group(1)),
                "title": match.group(2).strip(),
            }
        )
    return headings


def _extract_terms(text: str) -> list[str]:
    terms = re.findall(r"[A-Za-z][A-Za-z0-9+._-]{1,}|[\u4e00-\u9fff]{2,12}", text)
    return [term for term in terms if len(term.strip()) >= 2]


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
