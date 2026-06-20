#!/usr/bin/env python3
"""Build a WeChat article seed matrix CSV from structured material JSON files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


FIELDNAMES = [
    "day",
    "slot",
    "seed_id",
    "content_pool",
    "topic",
    "pain_point",
    "solution",
    "hook",
    "mother_topic_prompt",
    "variant_ids_to_generate",
    "expected_article_count",
    "primary_account_type",
    "backup_account_types",
    "hook_package",
    "primary_hook_ids",
    "cta_strategy",
    "publishing_note",
]


DEFAULT_VARIANTS = "|".join(f"V{i:02d}" for i in range(1, 11))
ACCOUNT_ROTATION = ["趋势号", "教程号", "案例号", "强CTA号", "平台选择号", "副业号", "工具号"]
ANGLE_VARIANTS = [
    ("避坑清单版", "把常见错误拆成可检查清单，突出哪些行为必须立刻停止。"),
    ("案例复盘版", "用一个典型新手场景复盘问题链路，突出错误决策如何放大损失。"),
    ("时间线版", "按第 1 天、第 3 天、第 7 天、第 30 天组织行动顺序。"),
    ("误区纠正版", "先提出反常识判断，再逐条纠正常见误解。"),
    ("决策指南版", "给出判断标准、选择优先级和不该做的选项。"),
    ("预算取舍版", "围绕低成本、高必要性和不值得买展开。"),
    ("家庭协作版", "把问题放到家庭分工、老人孩子参与和日常执行中讨论。"),
    ("新手问答版", "用连续问答解决新手最容易犹豫的关键问题。"),
    ("风险预警版", "突出不处理会造成的健康、安全或关系风险。"),
    ("步骤 SOP 版", "给出可以照着执行的流程、检查点和复盘方式。"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-dir", action="append", required=True, help="material/<date> directory; repeatable")
    parser.add_argument("--output", required=True, help="output CSV path")
    parser.add_argument("--start-seed", default="S001", help="first seed ID, e.g. S001")
    parser.add_argument("--start-day", default="D01", help="first day ID, e.g. D01")
    parser.add_argument("--slots-per-day", type=int, default=3, help="number of seeds per day")
    parser.add_argument("--seeds-per-material", type=int, default=1, help="topic seeds to generate per material file")
    parser.add_argument("--max-seeds", type=int, help="optional maximum number of seeds")
    parser.add_argument("--variant-ids", default=DEFAULT_VARIANTS, help="pipe-separated variant IDs")
    parser.add_argument("--expected-article-count", default="10", help="planned article count per seed")
    parser.add_argument("--hook-package", default="", help="optional hook package name")
    parser.add_argument("--primary-hook-ids", default="", help="optional pipe-separated hook IDs")
    parser.add_argument("--force", action="store_true", help="overwrite output if it already exists")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report and skip malformed local material.
        print(f"WARN skip invalid JSON: {path}: {exc}")
        return None


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def clean_text(value: Any, max_len: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = "、".join(clean_text(item) for item in value if clean_text(item))
    elif isinstance(value, dict):
        parts = [clean_text(item) for item in value.values()]
        value = "、".join(part for part in parts if part)
    else:
        value = str(value)
    text = re.sub(r"\s+", " ", value).strip()
    if max_len and len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def phrase(value: str) -> str:
    return clean_text(value).rstrip("。！？；;，,、 ")


def natural_key(path: Path) -> list[int | str]:
    parts = re.split(r"(\d+)", path.name)
    return [int(part) if part.isdigit() else part for part in parts]


def first_value(items: list[Any], keys: list[str]) -> str:
    for item in items:
        if isinstance(item, dict):
            for key in keys:
                text = clean_text(item.get(key))
                if text:
                    return text
        else:
            text = clean_text(item)
            if text:
                return text
    return ""


def material_title(data: dict[str, Any], path: Path) -> str:
    meta = data.get("元数据") if isinstance(data.get("元数据"), dict) else {}
    return clean_text(meta.get("标题")) or path.stem


def material_tags(data: dict[str, Any]) -> list[str]:
    meta = data.get("元数据") if isinstance(data.get("元数据"), dict) else {}
    tags = [clean_text(item) for item in as_list(meta.get("标签"))]
    categories = [clean_text(item) for item in as_list(meta.get("分类"))]
    return [item for item in tags + categories if item]


def material_topics(data: dict[str, Any], title: str) -> list[str]:
    topics = [clean_text(item) for item in as_list(data.get("选题")) if clean_text(item)]
    return topics or [title]


def expand_topics(topics: list[str], target_count: int) -> list[tuple[str, str]]:
    """Return (topic, angle_note) pairs, expanding finite source topics deterministically."""
    base_topics = [phrase(topic) for topic in topics if phrase(topic)]
    if not base_topics:
        return []

    expanded: list[tuple[str, str]] = [(topic, "") for topic in base_topics]
    if target_count <= len(expanded):
        return expanded[:target_count]

    round_index = 0
    while len(expanded) < target_count:
        angle_name, angle_note = ANGLE_VARIANTS[round_index % len(ANGLE_VARIANTS)]
        for topic in base_topics:
            if len(expanded) >= target_count:
                break
            expanded.append((f"{topic}｜{angle_name}", angle_note))
        round_index += 1
    return expanded


def summarize_material(data: dict[str, Any]) -> dict[str, str]:
    summary = data.get("总结") if isinstance(data.get("总结"), dict) else {}
    hotspot = clean_text(summary.get("核心热点")) or first_value(data.get("蹭到的热点", []), ["热点", "说明", "关键词"])
    pain = clean_text(summary.get("核心痛点")) or first_value(data.get("痛点", []), ["痛点", "说明", "对应内容"])
    solution = clean_text(summary.get("核心解决方案")) or first_value(data.get("解决方案", []), ["方案", "说明", "关键步骤", "执行步骤"])
    positioning = clean_text(data.get("文章定位"))
    return {
        "hotspot": hotspot,
        "pain": pain,
        "solution": solution,
        "positioning": positioning,
    }


def infer_content_pool(topic: str, data: dict[str, Any], title: str) -> str:
    tags = material_tags(data)
    if topic:
        return clean_text(topic, 28)
    if tags:
        return clean_text(tags[0], 28)
    return clean_text(title, 28)


def infer_account_type(text: str) -> str:
    if re.search(r"赛事|参赛|报名|奖励|入围|提交|交付标准", text):
        return "强CTA号"
    if re.search(r"教程|攻略|流程|SOP|提示词|清单|方法|指南|保姆级", text, re.I):
        return "教程号"
    if re.search(r"测评|案例|复盘|我用|实战|拆解", text):
        return "案例号"
    if re.search(r"变现|月入|赚钱|副业|商业化|收入|成本|ROI", text, re.I):
        return "副业号"
    if re.search(r"平台|入驻|选择|生态|闭环", text):
        return "平台选择号"
    if re.search(r"工具|插件|模型|产品", text):
        return "工具号"
    return "趋势号"


def backup_account_types(primary: str) -> str:
    backups = [item for item in ACCOUNT_ROTATION if item != primary]
    return "|".join(backups[:3])


def make_prompt(topic: str, summary: dict[str, str], hook_package: str) -> str:
    topic = phrase(topic)
    hotspot = phrase(summary["hotspot"]) or "一个正在升温的行业变化"
    pain = phrase(summary["pain"]) or "目标读者不知道如何判断机会和行动路径"
    solution = phrase(summary["solution"]) or "给出一套可执行的方法或判断框架"
    cta_tail = phrase(hook_package) or "一个可执行的下一步行动"
    return (
        f"围绕{topic}写一篇公众号文章：先讲{hotspot}，再讲目标读者的痛点“{pain}”，"
        f"给出解决方案“{solution}”，最后自然承接{cta_tail}。"
    )


def apply_angle(prompt: str, angle_note: str) -> str:
    if not angle_note:
        return prompt
    return f"{prompt} 写作角度：{angle_note}"


def make_hook(summary: dict[str, str], hook_package: str, primary_hook_ids: str) -> str:
    if hook_package and primary_hook_ids:
        return f"{hook_package}（{primary_hook_ids}）：围绕解决方案给出具体收益，再承接下一步行动。"
    if hook_package:
        return f"{hook_package}：围绕解决方案给出具体收益，再承接下一步行动。"
    solution = phrase(summary["solution"]) or "文中的核心方法"
    return f"中性钩子：引导读者收藏、关注或咨询{solution}的具体落地方式；不添加默认二维码或报名入口。"


def parse_numbered_id(value: str, prefix: str) -> tuple[str, int, int]:
    match = re.fullmatch(rf"({re.escape(prefix)})(\d+)", value)
    if not match:
        raise SystemExit(f"ID 格式错误：{value}，预期类似 {prefix}001")
    digits = match.group(2)
    return match.group(1), int(digits), len(digits)


def numbered(prefix: str, number: int, width: int) -> str:
    return f"{prefix}{number:0{width}d}"


def iter_material_files(material_dirs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw_dir in material_dirs:
        material_dir = Path(raw_dir)
        if not material_dir.is_dir():
            raise SystemExit(f"material dir 不存在：{material_dir}")
        files.extend(sorted(material_dir.glob("*.json"), key=natural_key))
    return sorted(files, key=natural_key)


def build_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    if args.slots_per_day < 1:
        raise SystemExit("--slots-per-day must be >= 1")
    if args.seeds_per_material < 1:
        raise SystemExit("--seeds-per-material must be >= 1")

    seed_prefix, seed_start, seed_width = parse_numbered_id(args.start_seed, "S")
    day_prefix, day_start, day_width = parse_numbered_id(args.start_day, "D")

    rows: list[dict[str, str]] = []
    for path in iter_material_files(args.material_dir):
        data = load_json(path)
        if not data:
            continue
        title = material_title(data, path)
        topics = expand_topics(material_topics(data, title), args.seeds_per_material)
        summary = summarize_material(data)
        strategy_text = " ".join([title, *[topic for topic, _ in topics], *summary.values()])

        for topic, angle_note in topics:
            index = len(rows)
            if args.max_seeds is not None and index >= args.max_seeds:
                return rows
            day_offset, slot_offset = divmod(index, args.slots_per_day)
            seed_id = numbered(seed_prefix, seed_start + index, seed_width)
            day = numbered(day_prefix, day_start + day_offset, day_width)
            slot = str(slot_offset + 1)
            primary = infer_account_type(strategy_text)
            cta_strategy = (
                f"结合{args.hook_package}，先给出具体收益，再承接下一步行动。"
                if args.hook_package
                else "先给出可执行步骤，再承接收藏、关注或咨询。"
            )
            publishing_note = (
                f"同一母题的{args.expected_article_count}个变体分散到不同矩阵号；"
                "标题、开头、案例和CTA顺序必须变化，避免像同稿改写。"
            )
            rows.append(
                {
                    "day": day,
                    "slot": slot,
                    "seed_id": seed_id,
                    "content_pool": infer_content_pool(topic, data, title),
                    "topic": phrase(topic),
                    "pain_point": phrase(summary["pain"]) or "目标读者不知道如何判断机会和行动路径",
                    "solution": phrase(summary["solution"]) or "给出一套可执行的方法或判断框架",
                    "hook": make_hook(summary, args.hook_package, args.primary_hook_ids),
                    "mother_topic_prompt": apply_angle(
                        make_prompt(topic, summary, args.hook_package),
                        angle_note,
                    ),
                    "variant_ids_to_generate": args.variant_ids,
                    "expected_article_count": str(args.expected_article_count),
                    "primary_account_type": primary,
                    "backup_account_types": backup_account_types(primary),
                    "hook_package": args.hook_package,
                    "primary_hook_ids": args.primary_hook_ids,
                    "cta_strategy": cta_strategy,
                    "publishing_note": publishing_note,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"输出已存在，使用 --force 覆盖：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows = build_rows(args)
    if not rows:
        raise SystemExit("没有生成任何 seed，请检查 material dir 或 --max-seeds")
    output = Path(args.output)
    write_csv(output, rows, args.force)
    print(f"wrote {len(rows)} seeds to {output}")
    print(f"seed range: {rows[0]['seed_id']}..{rows[-1]['seed_id']}")


if __name__ == "__main__":
    main()
