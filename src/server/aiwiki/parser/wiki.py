# -*- coding: utf-8 -*-
"""Parse AI Wiki markdown files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..schemas import WikiEntryOut, WikiHomeOut, WikiReferenceOut
from .utils import (
    body_excerpt,
    extract_headings,
    extract_wikilinks,
    first_heading,
    parse_simple_frontmatter,
    relative,
    render_wikilinks,
    string,
)


def parse_wiki_entries(workdir: Path) -> list[WikiEntryOut]:
    wiki_root = workdir / "wiki"
    if not wiki_root.exists():
        return []

    entries: list[WikiEntryOut] = []
    for path in sorted(wiki_root.glob("**/*.md"), key=lambda item: item.as_posix()):
        if path.name in {"index.md", "log.md"} or path.name.upper() == "SCHEMA.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = split_frontmatter(text)
        title = string(frontmatter.get("title")) or first_heading(body) or path.stem
        sections = parse_sections(body)
        entries.append(
            WikiEntryOut(
                path=relative(path, workdir),
                slug=path.with_suffix("").relative_to(wiki_root).as_posix(),
                type=entry_type(path, frontmatter, wiki_root),
                title=title,
                frontmatter=frontmatter,
                body_markdown=body,
                excerpt=body_excerpt(body, sections),
                created=string(frontmatter.get("created")) or None,
                updated=string(frontmatter.get("updated")) or None,
                sections=sections,
                references=sorted(set(extract_wikilinks(body))),
            )
        )
    return entries


def parse_wiki_home(workdir: Path) -> WikiHomeOut | None:
    path = workdir / "wiki" / "index.md"
    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    body = clean_wiki_home_body(body)
    title = string(frontmatter.get("title")) or first_heading(body) or "AI Wiki"
    return WikiHomeOut(
        path=relative(path, workdir),
        title=title,
        body_markdown=body,
        references=sorted(set(extract_wikilinks(body))),
        headings=extract_headings(body),
    )


def attach_reference_links(entries: list[WikiEntryOut]) -> None:
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


def clean_wiki_home_body(body: str) -> str:
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


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    return parse_simple_frontmatter(raw), body


def parse_sections(body: str) -> list[dict[str, str]]:
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
            current_lines.append(render_wikilinks(line))
    if current_lines:
        sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})
    return [section for section in sections if section["content"]]


def entry_type(path: Path, frontmatter: dict[str, Any], wiki_root: Path) -> str:
    explicit_type = string(frontmatter.get("type"))
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
