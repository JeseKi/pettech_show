# -*- coding: utf-8 -*-
"""Workspace path and wiki initialization helpers."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status

from src.server.config import global_config


def new_job_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_personal_aiwiki"


def personal_aiwiki_root() -> Path:
    return Path(global_config.project_root) / "data" / "personal_aiwiki"


def user_root(owner_user_id: int) -> Path:
    return personal_aiwiki_root() / "users" / f"user_{owner_user_id}"


def user_workspace_root(owner_user_id: int) -> Path:
    return user_root(owner_user_id) / "workspace"


def user_job_dir(owner_user_id: int, job_id: str) -> Path:
    return user_root(owner_user_id) / "jobs" / job_id


def ensure_workspace(workspace_root: Path) -> None:
    wiki_root = workspace_root / "wiki"
    for folder in (
        workspace_root / "raw",
        wiki_root / "entities",
        wiki_root / "concepts",
        wiki_root / "comparisons",
        wiki_root / "queries",
    ):
        folder.mkdir(parents=True, exist_ok=True)
    schema_path = wiki_root / "SCHEMA.md"
    index_path = wiki_root / "index.md"
    log_path = wiki_root / "log.md"
    today = datetime.now(timezone.utc).date().isoformat()
    if not schema_path.exists():
        schema_path.write_text(DEFAULT_SCHEMA, encoding="utf-8")
    if not index_path.exists():
        index_path.write_text(
            f"---\ntitle: 个人知识库\ntype: index\ncreated: {today}\nupdated: {today}\ntags: [personal-ai-wiki]\n---\n\n# 个人知识库\n\n## 最近更新\n\n- 暂无整理内容。\n\n## 入口\n\n- [[queries/index|问答索引]]\n",
            encoding="utf-8",
        )
    query_index_path = wiki_root / "queries" / "index.md"
    if not query_index_path.exists():
        query_index_path.write_text(
            f"---\ntitle: 问答索引\ntype: query\ncreated: {today}\nupdated: {today}\ntags: [personal-ai-wiki]\n---\n\n# 问答索引\n\n暂无沉淀问答。\n",
            encoding="utf-8",
        )
    if not log_path.exists():
        log_path.write_text(f"# 个人 AI Wiki 日志\n\n- {today} 初始化个人 Wiki。\n", encoding="utf-8")


def resolve_wiki_page_path(wiki_root: Path, page: str) -> Path:
    normalized = normalize_wiki_page(page)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供词条路径")
    if normalized.startswith("/") or normalized.startswith("\\"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="词条路径非法")

    candidate = wiki_root / normalized
    if candidate.suffix.lower() != ".md":
        candidate = candidate.with_suffix(".md")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(wiki_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="词条路径非法") from exc
    return resolved


def normalize_wiki_page(page: str) -> str:
    text = page.strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    if "|" in text:
        text = text.split("|", 1)[0].strip()
    if "#" in text:
        text = text.split("#", 1)[0].strip()
    text = text.removeprefix("wiki/").removeprefix("./")
    return text


DEFAULT_SCHEMA = """# 个人 AI Wiki Schema

所有 Wiki 内容位于 `wiki/` 下，原始资料位于同级 `raw/` 下。原始资料只追加、不改写。

## 目录

- `index.md`：个人 Wiki 首页和主要入口。
- `log.md`：按时间记录导入和重要修订。
- `SCHEMA.md`：本文件，记录结构约定。
- `entities/`：人物、组织、产品、项目、地点等实体。
- `concepts/`：概念、方法、原则、事实卡。
- `comparisons/`：对比、权衡、决策记录。
- `queries/`：有长期价值的问题、答案和检索路径。

## 词条 frontmatter

```yaml
---
title: 词条标题
type: entity | concept | comparison | query | note | index
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [标签]
sources:
  - raw/260626/example.md
---
```

## 链接规范

- 使用 `[[folder/slug]]` 或 `[[folder/slug|展示文本]]` 连接相关词条。
- 新词条必须能从 `index.md` 或已有词条追溯到。
- 不确定的信息必须标注来源和置信度，不要写成定论。
"""
