#!/usr/bin/env python3
"""Validate Zhongying script creation capability output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = ["title", "capability_key", "summary", "sections", "next_actions"]
SCRIPT_CONTENT_KEYS = {
    "body",
    "content",
    "voiceover",
    "dialogue",
    "shot",
    "shots",
    "visual",
    "scenes",
    "正文",
    "口播",
    "镜头",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, help="Capability job workspace")
    parser.add_argument("--capability-key", required=True, help="Expected capability key")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only check that output/result.json is valid JSON with object top-level value.",
    )
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


def has_script_content(script: dict[str, Any]) -> bool:
    for key, value in script.items():
        if key in SCRIPT_CONTENT_KEYS and value:
            return True
        if isinstance(value, dict) and has_script_content(value):
            return True
        if isinstance(value, list) and any(item for item in value):
            return True
    return False


def validate_scene(scene: Any, index: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(scene, dict):
        return [f"scenes[{index}] must be an object"]
    title = scene.get("scene") or scene.get("title")
    visual = scene.get("visual") or scene.get("shot") or scene.get("镜头")
    voice = scene.get("voiceover") or scene.get("dialogue") or scene.get("口播")
    if not is_nonempty_string(title):
        errors.append(f"scenes[{index}] needs a scene/title")
    if not is_nonempty_string(visual):
        errors.append(f"scenes[{index}] needs visual/shot guidance")
    if not is_nonempty_string(voice):
        errors.append(f"scenes[{index}] needs voiceover/dialogue")
    return errors


def validate(workdir: Path, capability_key: str) -> list[str]:
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

    scenes = data.get("scenes")
    script = data.get("script")
    if isinstance(scenes, list) and scenes:
        for index, scene in enumerate(scenes, start=1):
            errors.extend(validate_scene(scene, index))
    elif isinstance(script, dict) and script and has_script_content(script):
        pass
    else:
        errors.append("result.json must include non-empty scenes or script content")
    return errors


def validate_json_only(workdir: Path) -> list[str]:
    errors: list[str] = []
    load_json(workdir / "output" / "result.json", errors)
    return errors


def main() -> int:
    args = parse_args()
    workdir = Path(args.workdir)
    errors = validate_json_only(workdir) if args.json_only else validate(workdir, args.capability_key)
    if errors:
        print("FAIL script creation output")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK script creation output JSON" if args.json_only else "OK script creation output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
