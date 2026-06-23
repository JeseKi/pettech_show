#!/usr/bin/env python3
"""Validate Zhongying topic planning capability output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = ["title", "capability_key", "summary", "sections", "topics", "next_actions"]
REQUIRED_TOPIC_FIELDS = ["title", "category", "total_score", "recommended_hook"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, help="Capability job workspace")
    parser.add_argument("--capability-key", required=True, help="Expected capability key")
    parser.add_argument("--min-topics", type=int, default=1, help="Minimum topic count")
    return parser.parse_args()


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"missing JSON result: {path}")
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"result.json is invalid JSON: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append("result.json must be a JSON object")
        return {}
    return parsed


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(workdir: Path, capability_key: str, min_topics: int) -> list[str]:
    errors: list[str] = []
    md_path = workdir / "output" / "result.md"
    json_path = workdir / "output" / "result.json"

    if not md_path.is_file():
        errors.append(f"missing Markdown result: {md_path}")
    elif not md_path.read_text(encoding="utf-8", errors="replace").strip():
        errors.append("result.md is empty")

    data = load_json(json_path, errors)
    if not data:
        return errors

    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            errors.append(f"result.json missing top-level field: {field}")

    if data.get("capability_key") != capability_key:
        errors.append(f"capability_key mismatch: {data.get('capability_key')!r} != {capability_key!r}")
    if not is_nonempty_string(data.get("title")):
        errors.append("title must be a non-empty string")
    if not isinstance(data.get("summary"), dict):
        errors.append("summary must be an object")
    if not isinstance(data.get("sections"), list) or not data.get("sections"):
        errors.append("sections must be a non-empty array")
    if not isinstance(data.get("next_actions"), list) or not data.get("next_actions"):
        errors.append("next_actions must be a non-empty array")

    topics = data.get("topics")
    if not isinstance(topics, list) or len(topics) < min_topics:
        errors.append(f"topics must contain at least {min_topics} item(s)")
        return errors

    seen_titles: set[str] = set()
    for index, topic in enumerate(topics, start=1):
        if not isinstance(topic, dict):
            errors.append(f"topics[{index}] must be an object")
            continue
        for field in REQUIRED_TOPIC_FIELDS:
            if field not in topic:
                errors.append(f"topics[{index}] missing field: {field}")
        title = topic.get("title")
        if not is_nonempty_string(title):
            errors.append(f"topics[{index}].title must be a non-empty string")
        elif title in seen_titles:
            errors.append(f"duplicate topic title: {title}")
        else:
            seen_titles.add(str(title))
        if not is_nonempty_string(topic.get("category")):
            errors.append(f"topics[{index}].category must be a non-empty string")
        if not is_nonempty_string(topic.get("recommended_hook")):
            errors.append(f"topics[{index}].recommended_hook must be a non-empty string")
        score = topic.get("total_score")
        if not isinstance(score, (int, float)):
            errors.append(f"topics[{index}].total_score must be numeric")
    return errors


def main() -> int:
    args = parse_args()
    errors = validate(Path(args.workdir), args.capability_key, args.min_topics)
    if errors:
        print("FAIL topic planning output")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK topic planning output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
