# -*- coding: utf-8 -*-
"""Shared parser helpers for AI Wiki artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..schemas import WikiEntryOut

WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def render_wikilinks(text: str) -> str:
    return WIKILINK_PATTERN.sub(lambda match: wikilink_label(match.group(1)), text)


def extract_wikilinks(text: str) -> list[str]:
    return [wikilink_slug(match) for match in WIKILINK_PATTERN.findall(text)]


def wikilink_slug(raw: str) -> str:
    return split_wikilink(raw)[0]


def wikilink_label(raw: str) -> str:
    slug, label = split_wikilink(raw)
    return label or slug


def split_wikilink(raw: str) -> tuple[str, str | None]:
    normalized = raw.replace("\\|", "|")
    if "|" not in normalized:
        return normalized.strip(), None
    slug, label = normalized.split("|", 1)
    return slug.strip(), label.strip() or None


def parse_simple_frontmatter(raw: str) -> dict[str, Any]:
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


def section_excerpt(entry: WikiEntryOut) -> str:
    for section in entry.sections:
        content = section.get("content", "").strip()
        if content:
            return content[:240]
    return ""


def body_excerpt(body: str, sections: list[dict[str, str]]) -> str:
    for section in sections:
        content = section.get("content", "").strip()
        if content:
            return content[:240]
    stripped_lines = [
        render_wikilinks(line).strip()
        for line in body.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return "\n".join(stripped_lines)[:240]


def extract_headings(body: str) -> list[dict[str, Any]]:
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


def extract_terms(text: str) -> list[str]:
    terms = re.findall(r"[A-Za-z][A-Za-z0-9+._-]{1,}|[\u4e00-\u9fff]{2,12}", text)
    return [term for term in terms if len(term.strip()) >= 2]


def first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
