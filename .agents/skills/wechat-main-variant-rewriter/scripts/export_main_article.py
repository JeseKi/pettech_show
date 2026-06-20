#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("data/database.db")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export one editorial main revision into an audience rewrite bundle."
    )
    parser.add_argument(
        "--revision-id",
        type=int,
        required=True,
        help="Main article revision ID.",
    )
    parser.add_argument(
        "--issue-id",
        type=int,
        help="Optional issue guard. Fails if the revision does not belong to this issue.",
    )
    parser.add_argument(
        "--audience",
        required=True,
        help="Audience segment name or ID.",
    )
    parser.add_argument(
        "--handoff-id",
        required=True,
        help="Stable handoff ID copied from the editorial OpenCode task.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--run-dir",
        help="Override run directory. Default: .opencode/runs/issues/<issue-id>/variants/<handoff-id>/<audience>",
    )
    parser.add_argument(
        "--output-dir",
        help="Override output directory. Default: .opencode/runs/issues/<issue-id>/variants/<handoff-id>/<audience>/output",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow resetting a non-empty run/output directory.",
    )
    return parser.parse_args()


def ensure_dir(path: Path, force: bool) -> None:
    if path.exists():
        has_files = any(path.iterdir())
        if has_files and not force:
            raise SystemExit(f"Directory already exists and is not empty: {path}")
        if has_files and force:
            shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "audience"


def build_default_run_dir(issue_id: int, handoff_id: str, audience: str) -> Path:
    return (
        Path(".opencode")
        / "runs"
        / "issues"
        / str(issue_id)
        / "variants"
        / handoff_id
        / slugify(audience)
    )


def build_default_output_dir(issue_id: int, handoff_id: str, audience_key: str) -> Path:
    return (
        Path(".opencode")
        / "runs"
        / "issues"
        / str(issue_id)
        / "variants"
        / handoff_id
        / audience_key
        / "output"
    )


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def parse_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_artwork_main_article(
    issue_id: int,
    revision_id: int,
    handoff_id: str,
) -> Path | None:
    artwork_root = Path(".opencode") / "runs" / "issues" / str(issue_id) / "artwork"
    if not artwork_root.exists() or not artwork_root.is_dir():
        return None

    candidates: list[tuple[int, float, Path]] = []
    for main_file in artwork_root.glob("*/output/main.md"):
        if not main_file.is_file():
            continue

        run_dir = main_file.parents[1]
        manifest = read_json_file(run_dir / "manifest.json")
        manifest_revision_id = parse_optional_int(manifest.get("main_revision_id"))
        manifest_issue_id = parse_optional_int(manifest.get("issue_id"))

        if manifest_revision_id is not None and manifest_revision_id != revision_id:
            continue
        if manifest_issue_id is not None and manifest_issue_id != issue_id:
            continue
        if manifest_revision_id is None and run_dir.name != handoff_id:
            continue

        priority = 1 if run_dir.name == handoff_id else 0
        candidates.append((priority, main_file.stat().st_mtime, main_file))

    if not candidates:
        return None
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1]), reverse=True)
    return candidates[0][2]


def resolve_source_article(
    revision: sqlite3.Row,
    handoff_id: str,
) -> tuple[str, dict[str, str]]:
    issue_id = int(revision["issue_id"])
    revision_id = int(revision["revision_id"])
    artwork_main = find_artwork_main_article(issue_id, revision_id, handoff_id)

    if artwork_main is not None:
        return artwork_main.read_text(encoding="utf-8"), {
            "kind": "artwork_main",
            "path": artwork_main.as_posix(),
        }

    return str(revision["markdown"] or ""), {
        "kind": "revision_markdown",
        "path": f"editorial_article_revisions:{revision_id}",
    }


def load_main_revision(conn: sqlite3.Connection, revision_id: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT
            r.id AS revision_id,
            r.article_id,
            r.revision_no,
            r.title,
            r.summary,
            r.markdown,
            r.metadata_json,
            a.issue_id,
            a.role,
            i.issue_date,
            i.theme,
            i.notes,
            i.source_bundle_id
        FROM editorial_article_revisions AS r
        JOIN editorial_articles AS a ON a.id = r.article_id
        JOIN editorial_issues AS i ON i.id = a.issue_id
        WHERE r.id = ?
        """,
        (revision_id,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"Revision not found: {revision_id}")
    if str(row["role"]).upper() != "MAIN":
        raise SystemExit(f"Revision {revision_id} is not a main article revision.")
    return row


def resolve_audience(conn: sqlite3.Connection, raw_audience: str) -> dict[str, Any]:
    audience = raw_audience.strip()
    if audience.isdigit():
        row = conn.execute(
            """
            SELECT id, name, description, prompt_profile
            FROM editorial_audience_segments
            WHERE id = ?
            """,
            (int(audience),),
        ).fetchone()
        if row is not None:
            return {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "description": str(row["description"] or ""),
                "prompt_profile": str(row["prompt_profile"] or ""),
            }
    row = conn.execute(
        """
        SELECT id, name, description, prompt_profile
        FROM editorial_audience_segments
        WHERE name = ?
        """,
        (audience,),
    ).fetchone()
    if row is not None:
        return {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "description": str(row["description"] or ""),
            "prompt_profile": str(row["prompt_profile"] or ""),
        }
    return {
        "id": None,
        "name": audience,
        "description": "",
        "prompt_profile": "",
    }


def safe_json_loads(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def load_source_items(
    conn: sqlite3.Connection,
    bundle_id: int | None,
    preferred_ids: list[int],
) -> list[sqlite3.Row]:
    if not bundle_id:
        return []
    rows = conn.execute(
        """
        SELECT
            id,
            source_type,
            source_label,
            source_ref_id,
            content_markdown,
            sort_order
        FROM editorial_source_items
        WHERE source_bundle_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (bundle_id,),
    ).fetchall()
    if not preferred_ids:
        return rows
    preferred = set(preferred_ids)
    filtered = [row for row in rows if int(row["id"]) in preferred]
    return filtered or rows


def render_task(
    revision: sqlite3.Row,
    handoff_id: str,
    audience: dict[str, Any],
    source_items: list[sqlite3.Row],
    output_dir: Path,
) -> str:
    source_lines = "\n".join(
        f"- [{item['id']}] {item['source_label']} ({item['source_type']})"
        for item in source_items
    )
    if not source_lines:
        source_lines = "- 当前没有关联素材，请以主稿正文为主要事实锚点。"
    return f"""# 变体改写任务

主稿信息：

- issue_id: {revision["issue_id"]}
- handoff_id: {handoff_id}
- issue_date: {revision["issue_date"]}
- theme: {revision["theme"]}
- main_revision_id: {revision["revision_id"]}
- main_revision_no: {revision["revision_no"]}
- main_title: {revision["title"]}
- issue_notes: {revision["notes"] or "无"}

目标人群：

- audience_label: {audience["name"]}
- audience_segment_id: {audience["id"] if audience["id"] is not None else "无"}
- audience_name: {audience["name"]}
- description: {audience["description"] or "无"}
- prompt_profile: {audience["prompt_profile"] or "无"}

可用素材：
{source_lines}

请先阅读：

- `source_article.md`
- `manifest.json`
- `sources/`

然后在输出目录中产出：

- `others.md`
- `metadata.json`

要求：

- 以 `source_article.md` 为事实锚点
- 原文中的营销/推广信息必须全部保留，并结合目标受众做自然改写，不能删除、硬切，不能比原文少
- 原文中的图片必须全部保留；如果原文里有图片 Markdown 或图片占位，变体里也必须保留，不能缺少任何一张
- 营销/推广信息和图片都属于强制保留项，两类内容一个都不能少
- 受众角度必须明显变化，但正文里不要直说“这是给某某人看的”
- `metadata.json` 从 `metadata.template.json` 开始填写
- `metadata.json` 顶层 `handoff_id` 必须保留为 `{handoff_id}`
- `metadata.json` 中的 `source_item_ids` 只填写真实使用到的素材项
- 写完后执行：
  `python3 .agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py --run-dir {output_dir.parent.as_posix()}`

输出目录：`{output_dir}`
"""


def metadata_template(
    revision: sqlite3.Row,
    handoff_id: str,
    audience: dict[str, Any],
    source_items: list[sqlite3.Row],
) -> str:
    payload = {
        "issue_id": int(revision["issue_id"]),
        "issue_date": str(revision["issue_date"]),
        "handoff_id": handoff_id,
        "main_revision_id": int(revision["revision_id"]),
        "audience_label": str(audience["name"]),
        "article": {
            "role": "variant",
            "file": "others.md",
            "title": "",
            "summary": "",
            "tags": [],
            "based_on_revision_id": int(revision["revision_id"]),
            "source_item_ids": [int(item["id"]) for item in source_items],
        },
    }
    if audience["id"] is not None:
        payload["audience_segment_id"] = int(audience["id"])
        payload["audience_segment_name"] = str(audience["name"])
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        revision = load_main_revision(conn, args.revision_id)
        if args.issue_id is not None and int(revision["issue_id"]) != args.issue_id:
            raise SystemExit(
                f"Issue mismatch: expected {args.issue_id}, actual {revision['issue_id']}"
            )
        audience = resolve_audience(conn, args.audience)
        metadata = safe_json_loads(revision["metadata_json"])
        preferred_ids = metadata.get("source_item_ids") or []
        if not isinstance(preferred_ids, list):
            preferred_ids = []
        source_items = load_source_items(
            conn,
            revision["source_bundle_id"],
            [int(item) for item in preferred_ids if str(item).isdigit()],
        )
    finally:
        conn.close()

    run_dir = (
        Path(args.run_dir)
        if args.run_dir
        else build_default_run_dir(
            int(revision["issue_id"]),
            args.handoff_id,
            str(audience["name"]),
        )
    )
    audience_key = slugify(str(audience["name"]))
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else build_default_output_dir(
            int(revision["issue_id"]), args.handoff_id, audience_key
        )
    )
    ensure_dir(run_dir, force=args.force)
    ensure_dir(output_dir, force=args.force)

    source_article, source_article_info = resolve_source_article(
        revision,
        args.handoff_id,
    )

    exported_sources: list[dict[str, Any]] = []
    for item in source_items:
        relative_path = Path("sources") / f"{item['sort_order']:03d}_{item['id']}.md"
        write_text(run_dir / relative_path, str(item["content_markdown"] or ""))
        exported_sources.append(
            {
                "source_item_id": int(item["id"]),
                "source_type": str(item["source_type"]),
                "source_label": str(item["source_label"]),
                "source_ref_id": str(item["source_ref_id"] or ""),
                "local_file": relative_path.as_posix(),
            }
        )

    manifest = {
        "issue_id": int(revision["issue_id"]),
        "handoff_id": args.handoff_id,
        "main_revision_id": int(revision["revision_id"]),
        "audience_label": str(audience["name"]),
        "run_dir": run_dir.as_posix(),
        "output_dir": output_dir.as_posix(),
        "expected_outputs": ["others.md", "metadata.json"],
        "source_article": source_article_info,
        "exported_sources": exported_sources,
    }
    if audience["id"] is not None:
        manifest["audience_segment_id"] = int(audience["id"])

    write_text(
        run_dir / "task.md",
        render_task(revision, args.handoff_id, audience, source_items, output_dir),
    )
    write_text(run_dir / "source_article.md", source_article)
    write_text(
        run_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    write_text(
        run_dir / "metadata.template.json",
        metadata_template(revision, args.handoff_id, audience, source_items),
    )

    print(f"Run directory: {run_dir}")
    print(f"Output directory: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
