#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate one variant run directory output contract."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Variant run directory that contains task.md / manifest.json / output/.",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=0,
        help="Optional minimum Chinese characters required in others.md. Default: 0 (disabled).",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def count_image_markers(text: str) -> int:
    markdown_images = re.findall(r"!\[[^\]]*\]\([^)]+\)", text)
    html_images = re.findall(r"<img\b", text, flags=re.IGNORECASE)
    return len(markdown_images) + len(html_images)


def count_fenced_code_blocks(text: str) -> int:
    return len(re.findall(r"```", text)) // 2


def internal_terms_in(text: str) -> list[str]:
    forbidden = [
        "source_article",
        "源文",
        "源稿",
        "原文",
        "改写任务",
        "变体改写",
        "叙事模板",
        "本文采用",
        "钩子",
        "hook",
    ]
    return [term for term in forbidden if term in text]


SEARCH_INTENT_REQUIRED_FIELDS = [
    "意图类型",
    "关键词",
    "搜索意图",
    "适合文章角度",
    "标题使用建议",
    "优先级",
    "来源依据",
]
ALLOWED_SEARCH_INTENT_TYPES = {
    "痛点型",
    "教程型",
    "对比型",
    "替代品型",
    "值不值型",
    "问题排查型",
    "人群场景型",
    "趋势观点型",
}


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)

    errors: list[str] = []
    warnings: list[str] = []

    if not run_dir.exists() or not run_dir.is_dir():
        print(f"ERROR: run directory not found: {run_dir}")
        return 2

    task_file = run_dir / "task.md"
    manifest_file = run_dir / "manifest.json"
    source_article_file = run_dir / "source_article.md"
    metadata_template_file = run_dir / "metadata.template.json"

    for required in [
        task_file,
        manifest_file,
        source_article_file,
        metadata_template_file,
    ]:
        if not required.exists():
            errors.append(f"missing required run file: {required}")

    manifest: dict[str, Any] = {}
    if manifest_file.exists():
        try:
            manifest = load_json(manifest_file)
        except json.JSONDecodeError as exc:
            errors.append(f"manifest.json is invalid JSON: {exc}")

    sources_dir = run_dir / "sources"
    if manifest.get("input_mode") != "filesystem":
        if not sources_dir.exists() or not sources_dir.is_dir():
            warnings.append(f"sources directory missing: {sources_dir}")

    output_dir = run_dir / "output"
    if isinstance(manifest.get("output_dir"), str) and manifest.get("output_dir"):
        output_dir = Path(str(manifest["output_dir"]))

    others_file = output_dir / "others.md"
    metadata_file = output_dir / "metadata.json"

    if not others_file.exists():
        errors.append(f"missing output file: {others_file}")
    if not metadata_file.exists():
        errors.append(f"missing output file: {metadata_file}")

    others_text = ""
    if others_file.exists():
        others_text = others_file.read_text(encoding="utf-8")
        if args.min_chars > 0:
            chinese_chars = count_chinese_chars(others_text)
            if chinese_chars < args.min_chars:
                errors.append(
                    f"others.md Chinese chars too short: {chinese_chars} < {args.min_chars}"
                )
        if len(others_text.strip()) == 0:
            errors.append("others.md is empty")

    metadata: dict[str, Any] = {}
    if metadata_file.exists():
        try:
            metadata = load_json(metadata_file)
        except json.JSONDecodeError as exc:
            errors.append(f"metadata.json is invalid JSON: {exc}")

    if others_text and source_article_file.exists():
        source_text = source_article_file.read_text(encoding="utf-8")
        source_image_count = count_image_markers(source_text)
        output_image_count = count_image_markers(others_text)
        if output_image_count < source_image_count:
            errors.append(
                "others.md contains fewer image references than source_article.md: "
                f"{output_image_count} < {source_image_count}"
            )

        source_code_count = count_fenced_code_blocks(source_text)
        output_code_count = count_fenced_code_blocks(others_text)
        if output_code_count < source_code_count:
            errors.append(
                "others.md contains fewer fenced code blocks than source_article.md: "
                f"{output_code_count} < {source_code_count}"
            )

    if others_text:
        leaked_terms = internal_terms_in(others_text)
        if leaked_terms:
            errors.append(
                "others.md exposes internal source/rewrite terminology: "
                + ", ".join(leaked_terms)
            )

    if metadata:
        input_mode = metadata.get("input_mode") or manifest.get("input_mode")
        filesystem_mode = input_mode == "filesystem"

        if filesystem_mode:
            required_top_keys = [
                "input_mode",
                "output_id",
                "audience_label",
                "article",
            ]
        else:
            required_top_keys = [
                "issue_id",
                "issue_date",
                "handoff_id",
                "main_revision_id",
                "audience_label",
                "article",
            ]
        for key in required_top_keys:
            if key not in metadata:
                errors.append(f"metadata.json missing key: {key}")

        article = metadata.get("article")
        if not isinstance(article, dict):
            errors.append("metadata.json field 'article' must be an object")
            article = {}

        required_article_keys = ["role", "file", "title", "summary", "tags"]
        if filesystem_mode:
            required_article_keys.append("based_on_output_id")
        else:
            required_article_keys.extend(["based_on_revision_id", "source_item_ids"])

        for key in required_article_keys:
            if key not in article:
                errors.append(f"metadata.json article missing key: {key}")

        if article.get("role") != "variant":
            errors.append("metadata.json article.role must be 'variant'")
        if article.get("file") != "others.md":
            errors.append("metadata.json article.file must be 'others.md'")

        if not str(article.get("title", "")).strip():
            errors.append("metadata.json article.title must not be empty")
        if not str(article.get("summary", "")).strip():
            errors.append("metadata.json article.summary must not be empty")

        tags = article.get("tags")
        if not isinstance(tags, list) or not tags:
            errors.append("metadata.json article.tags must be a non-empty array")

        search_intents = article.get("search_intents")
        if search_intents is not None:
            if not isinstance(search_intents, list):
                errors.append("metadata.json article.search_intents must be an array")
                search_intents = []
            for index, item in enumerate(search_intents, start=1):
                prefix = f"metadata.json article.search_intents[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                role = item.get("role")
                if role is not None and role not in {"primary", "secondary"}:
                    errors.append(f"{prefix}.role must be primary or secondary")
                intent_type = item.get("意图类型")
                if intent_type is not None and intent_type not in ALLOWED_SEARCH_INTENT_TYPES:
                    errors.append(f"{prefix}.意图类型 is not allowed: {intent_type}")
                for field in SEARCH_INTENT_REQUIRED_FIELDS:
                    value = item.get(field)
                    if value is not None and not str(value).strip():
                        errors.append(f"{prefix}.{field} must not be empty when present")

        source_item_ids = article.get("source_item_ids")
        if not filesystem_mode:
            if not isinstance(source_item_ids, list):
                errors.append("metadata.json article.source_item_ids must be an array")
                source_item_ids = []

            if any(not isinstance(item, int) for item in source_item_ids):
                errors.append(
                    "metadata.json article.source_item_ids must contain only integers"
                )

            exported = manifest.get("exported_sources") if manifest else None
            if isinstance(exported, list) and exported:
                valid_source_ids = {
                    item.get("source_item_id")
                    for item in exported
                    if isinstance(item, dict)
                    and isinstance(item.get("source_item_id"), int)
                }
                unknown_ids = [
                    item for item in source_item_ids if item not in valid_source_ids
                ]
                if unknown_ids:
                    errors.append(
                        f"metadata.json source_item_ids contain unknown IDs: {unknown_ids}"
                    )

        if manifest:
            if filesystem_mode:
                if metadata.get("input_mode") != "filesystem":
                    errors.append("metadata.json input_mode must be 'filesystem'")
                if metadata.get("output_id") != manifest.get("output_id"):
                    errors.append(
                        "metadata.json output_id does not match manifest output_id"
                    )
                if article.get("based_on_output_id") != manifest.get("output_id"):
                    errors.append(
                        "metadata.json article.based_on_output_id does not match manifest output_id"
                    )
            else:
                if metadata.get("handoff_id") != manifest.get("handoff_id"):
                    errors.append(
                        "metadata.json handoff_id does not match manifest handoff_id"
                    )
                if metadata.get("main_revision_id") != manifest.get("main_revision_id"):
                    errors.append(
                        "metadata.json main_revision_id does not match manifest main_revision_id"
                    )
            if metadata.get("audience_label") != manifest.get("audience_label"):
                errors.append(
                    "metadata.json audience_label does not match manifest audience_label"
                )

    if warnings:
        for warning in warnings:
            print(f"WARN: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"FAILED: {run_dir}")
        return 1

    print(f"OK: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
