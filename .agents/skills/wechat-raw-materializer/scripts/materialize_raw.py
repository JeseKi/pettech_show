#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_TOP_LEVEL = ["元数据", "文章定位", "痛点", "蹭到的热点", "解决方案", "选题", "总结"]
TOPIC_FIELD = "选题"
SEARCH_INTENT_FIELD = "搜索入口"
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
QUESTION_TOPIC_MARKERS = (
    "怎么",
    "如何",
    "为什么",
    "怎么办",
    "怎样",
    "能否",
    "是否",
    "能不能",
    "该不该",
    "要不要",
    "值不值",
    "够不够",
    "适不适合",
    "适合谁",
    "哪",
    "谁",
    "吗",
)
QUESTION_TOPIC_ENDINGS = (
    "?",
    "？",
    "怎么办",
    "怎么做",
    "怎么选",
    "如何做",
    "如何选",
    "值不值",
    "够不够",
    "行不行",
    "能不能",
    "该不该",
    "要不要",
    "适合谁",
)


def validate_topics(data: dict, material_path: Path, strict_question_topics: bool) -> list[str]:
    topics = data.get(TOPIC_FIELD)
    if not isinstance(topics, list) or not topics:
        return [f"MISSING or empty {TOPIC_FIELD} {material_path.as_posix()}"]

    errors: list[str] = []
    for index, topic in enumerate(topics, start=1):
        prefix = f"{material_path.as_posix()} {TOPIC_FIELD}[{index}]"
        if not isinstance(topic, str) or not topic.strip():
            errors.append(f"BAD {prefix}: must be a non-empty string")
            continue
        if strict_question_topics and not is_question_topic(topic):
            errors.append(f"BAD {prefix}: must be a complete question, not a label: {topic}")
    return errors


def is_question_topic(topic: str) -> bool:
    normalized = re.sub(r"\s+", "", topic.strip())
    if not normalized:
        return False
    if normalized.endswith(QUESTION_TOPIC_ENDINGS):
        return True
    return any(marker in normalized for marker in QUESTION_TOPIC_MARKERS)


def validate_search_intents(data: dict, material_path: Path) -> list[str]:
    search_intents = data.get(SEARCH_INTENT_FIELD)
    if not isinstance(search_intents, list) or not search_intents:
        return [f"MISSING or empty {SEARCH_INTENT_FIELD} {material_path.as_posix()}"]

    errors: list[str] = []
    for index, item in enumerate(search_intents, start=1):
        prefix = f"{material_path.as_posix()} {SEARCH_INTENT_FIELD}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"BAD {prefix}: item must be an object")
            continue

        for field in SEARCH_INTENT_REQUIRED_FIELDS:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"BAD {prefix}.{field}: must be a non-empty string")

        intent_type = item.get("意图类型")
        if isinstance(intent_type, str) and intent_type.strip() not in ALLOWED_SEARCH_INTENT_TYPES:
            allowed = ", ".join(sorted(ALLOWED_SEARCH_INTENT_TYPES))
            errors.append(f"BAD {prefix}.意图类型: {intent_type} (allowed: {allowed})")

    return errors


def project_root() -> Path:
    return Path.cwd()


def git_status_paths(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        raw_path = line[3:].strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        path = Path(raw_path)
        if len(path.parts) >= 2 and path.parts[0] == "raw":
            paths.append(path)
    return paths


def raw_markdown_files(root: Path, date: str | None, include_all: bool) -> list[Path]:
    candidates: set[Path] = set()

    if date:
        candidates.update(Path("raw", date).glob("*.md"))

    if include_all or not candidates:
        for path in git_status_paths(root):
            full = root / path
            if full.is_dir():
                candidates.update(path.glob("*.md"))
            elif path.suffix == ".md":
                candidates.add(path)

    normalized = []
    for path in candidates:
        if path.suffix == ".md" and len(path.parts) >= 3 and path.parts[0] == "raw":
            normalized.append(path)
    return sorted(set(normalized), key=lambda p: p.as_posix())


def material_files_for_date(date: str) -> list[Path]:
    return sorted(Path("material", date).glob("*.json"), key=lambda p: p.as_posix())


def referenced_raw_paths(date: str) -> dict[str, Path]:
    refs: dict[str, Path] = {}
    for path in material_files_for_date(date):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw_path = data.get("元数据", {}).get("raw文件路径")
        except Exception:
            continue
        if isinstance(raw_path, str):
            refs[raw_path] = path
    return refs


def existing_numbers(date: str) -> set[int]:
    numbers = set()
    pattern = re.compile(rf"^{re.escape(date)}_(\d+)_")
    for path in material_files_for_date(date):
        match = pattern.match(path.name)
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def clean_title(stem: str, date: str) -> tuple[int | None, str]:
    match = re.match(rf"^{re.escape(date)}_(\d+)_(.+)$", stem)
    number = int(match.group(1)) if match else None
    title = match.group(2) if match else stem
    title = title.replace("/", "／").replace("\u0000", "")
    title = title.replace("“", "").replace("”", "")
    title = re.sub(r"\s+", " ", title).strip()
    return number, title


def target_for_raw(raw_path: Path, next_number: int, used_numbers: set[int]) -> tuple[Path, int]:
    date = raw_path.parts[1]
    preferred_number, title = clean_title(raw_path.stem, date)
    number = preferred_number if preferred_number and preferred_number not in used_numbers else next_number
    target = Path("material", date, f"{date}_{number}_{title}.json")
    return target, number


def plan(args: argparse.Namespace) -> int:
    root = project_root()
    raw_files = raw_markdown_files(root, args.date, args.all)
    if not raw_files:
        print("No raw Markdown files found from git status or --date.", file=sys.stderr)
        return 1

    grouped: dict[str, list[Path]] = {}
    for raw_path in raw_files:
        grouped.setdefault(raw_path.parts[1], []).append(raw_path)

    for date, files in sorted(grouped.items()):
        refs = referenced_raw_paths(date)
        used_numbers = existing_numbers(date)
        next_number = max(used_numbers, default=0) + 1
        print(f"[{date}]")
        for raw_path in files:
            raw_key = raw_path.as_posix()
            if raw_key in refs:
                print(f"  exists  {raw_key} -> {refs[raw_key].as_posix()}")
                continue
            while next_number in used_numbers:
                next_number += 1
            target, assigned = target_for_raw(raw_path, next_number, used_numbers)
            used_numbers.add(assigned)
            next_number = max(next_number, assigned + 1)
            print(f"  create  {raw_key} -> {target.as_posix()}")
    return 0


def validate(args: argparse.Namespace) -> int:
    root = project_root()
    dates: set[str] = set()
    if args.date:
        dates.add(args.date)
    else:
        dates.update(path.parts[1] for path in Path("raw").glob("*/*.md"))

    ok = True
    for date in sorted(dates):
        refs = referenced_raw_paths(date)
        for raw_path in sorted(Path("raw", date).glob("*.md"), key=lambda p: p.as_posix()):
            if raw_path.as_posix() not in refs:
                ok = False
                print(f"MISSING material for {raw_path.as_posix()}")

        for material_path in material_files_for_date(date):
            try:
                data = json.loads(material_path.read_text(encoding="utf-8"))
            except Exception as exc:
                ok = False
                print(f"INVALID JSON {material_path.as_posix()}: {exc}")
                continue
            missing = [field for field in REQUIRED_TOP_LEVEL if field not in data]
            if missing:
                ok = False
                print(f"MISSING fields {material_path.as_posix()}: {', '.join(missing)}")
            raw_ref = data.get("元数据", {}).get("raw文件路径")
            if not isinstance(raw_ref, str) or not (root / raw_ref).is_file():
                ok = False
                print(f"BAD raw文件路径 {material_path.as_posix()}: {raw_ref}")
            for error in validate_topics(data, material_path, args.strict_question_topics):
                ok = False
                print(error)
            if args.strict_search_intents:
                for error in validate_search_intents(data, material_path):
                    ok = False
                    print(error)

    if ok:
        print("OK")
        return 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan and validate raw Markdown to material JSON conversion.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--date", help="Limit to raw/<YYMMDD>/")
    plan_parser.add_argument("--all", action="store_true", help="Inspect all raw files instead of only git status paths.")
    plan_parser.set_defaults(func=plan)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--date", help="Limit to raw/<YYMMDD>/")
    validate_parser.add_argument(
        "--strict-search-intents",
        action="store_true",
        help=f"Require a well-formed {SEARCH_INTENT_FIELD} array in every checked material JSON.",
    )
    validate_parser.add_argument(
        "--strict-question-topics",
        action="store_true",
        help=f"Require every {TOPIC_FIELD} item to be written as a complete question.",
    )
    validate_parser.set_defaults(func=validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
