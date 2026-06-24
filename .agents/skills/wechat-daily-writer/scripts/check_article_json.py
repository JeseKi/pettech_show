#!/usr/bin/env python3
"""Check WeChat daily writer metadata JSON files only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--article-dir",
        help="Article directory such as main/260620/260620_1. Defaults to latest main/*/*.",
    )
    parser.add_argument(
        "--include-variants",
        action="store_true",
        help="Also check variants/*/output/metadata.json under the article directory.",
    )
    return parser.parse_args()


def resolve_article_dir(value: str | None) -> Path:
    if value:
        path = Path(value)
        if not path.is_dir():
            raise FileNotFoundError(f"article directory not found: {path}")
        return path

    candidates = sorted(Path("main").glob("*/*/metadata.json"), key=lambda p: p.as_posix())
    if not candidates:
        raise FileNotFoundError("no article metadata found under main/*/*/metadata.json")
    return candidates[-1].parent


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing metadata JSON: {path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"metadata JSON must be an object: {path}")
    return parsed


def main() -> int:
    args = parse_args()
    try:
        article_dir = resolve_article_dir(args.article_dir)
        paths = [article_dir / "metadata.json"]
        if args.include_variants:
            paths.extend(sorted((article_dir / "variants").glob("*/output/metadata.json")))
        if args.include_variants and len(paths) == 1:
            raise FileNotFoundError(f"no variant metadata found under: {article_dir / 'variants'}")
        for path in paths:
            load_json_object(path)
    except Exception as exc:
        print(f"FAIL article metadata JSON: {exc}")
        return 1

    print(f"OK article metadata JSON files={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
