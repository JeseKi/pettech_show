#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any


DEFAULT_ANGLE_KEYS = [
    "problem-diagnosis",
    "case-replay",
    "cost-accounting",
    "method-breakdown",
    "category-map",
    "checklist-selfcheck",
    "counterintuitive",
    "trend-judgment",
    "decision-comparison",
]


ANGLE_TEMPLATES: dict[str, dict[str, str]] = {
    "problem-diagnosis": {
        "label": "问题诊断型",
        "slug": "problem-diagnosis",
        "opening_rule": "从一个常见错误、失败动作或误判切入。",
        "structure_rule": "常见错误 -> 为什么会失败 -> 判断标准 -> 正确路径 -> 下一步行动。",
        "hook_rule": "把转化承接放在正确路径或下一步行动里，不要只堆在文末。",
        "best_for": "教程、工具、风险、效率、使用方法类文章。",
        "avoid": "不要按源文顺序平铺素材；不要写成泛泛科普。",
    },
    "case-replay": {
        "label": "案例复盘型",
        "slug": "case-replay",
        "opening_rule": "从一个具体人物、场景、项目或失败瞬间切入。",
        "structure_rule": "具体场景 -> 失败过程 -> 原因倒推 -> 正确做法 -> 更稳的落地路径。",
        "hook_rule": "把转化承接包装成复盘后的更稳处理方式。",
        "best_for": "风险、踩坑、失败经验、转化导向文章。",
        "avoid": "不要写成虚构故事合集；场景必须服务源稿事实。",
    },
    "cost-accounting": {
        "label": "成本账型",
        "slug": "cost-accounting",
        "opening_rule": "从表面收益与隐藏成本的反差切入。",
        "structure_rule": "表面收益 -> 隐藏成本 -> 错误选择后果 -> 更优方案 -> 降低成本的下一步。",
        "hook_rule": "把转化承接放在降低成本、降低风险或提高确定性的段落里。",
        "best_for": "省钱、省时间、工具稳定性、效率、ROI 类文章。",
        "avoid": "不要只重复风险清单；必须把成本账算清楚。",
    },
    "method-breakdown": {
        "label": "方法论拆解型",
        "slug": "method-breakdown",
        "opening_rule": "先给一个可迁移的总原则。",
        "structure_rule": "总原则 -> 3-5 个模块 -> 每个模块为什么有效 -> 可复用方法 -> 工具/服务承接。",
        "hook_rule": "把转化承接放在方法落地或工具/服务承接处。",
        "best_for": "prompt、工作流、教程、知识拆解、产品使用类文章。",
        "avoid": "不要只罗列模板；每个模块都要解释为什么有效。",
    },
    "category-map": {
        "label": "分类地图型",
        "slug": "category-map",
        "opening_rule": "从为什么必须先分类、不能混在一起比较切入。",
        "structure_rule": "分类框架 -> 每类适用场景/风险/价值 -> 选择路径 -> 推荐落地方式。",
        "hook_rule": "把转化承接放在选择路径的推荐分支里。",
        "best_for": "多方案、多模板、多风险、多工具对比类文章。",
        "avoid": "不要写成简单合集；分类必须改变读者判断方式。",
    },
    "checklist-selfcheck": {
        "label": "清单自查型",
        "slug": "checklist-selfcheck",
        "opening_rule": "用一个读者可以立刻回答的自查问题开头。",
        "structure_rule": "自查问题 -> 5-7 个判断项 -> 错误/正确做法 -> 行动路径 -> 领取方式或工具入口。",
        "hook_rule": "把转化承接放在自查后的下一步行动里。",
        "best_for": "避坑、工具配置、质量检查、收藏转发类文章。",
        "avoid": "不要把清单写成源文段落的换行版。",
    },
    "counterintuitive": {
        "label": "反常识型",
        "slug": "counterintuitive",
        "opening_rule": "先否定一个常见但错误或不完整的判断。",
        "structure_rule": "常见判断 -> 真正变量 -> 重新排序优先级 -> 新判断标准 -> 下一步选择。",
        "hook_rule": "把转化承接放在新判断标准的自然延伸里。",
        "best_for": "有认知反转、优先级变化、误区纠偏的文章。",
        "avoid": "不要为了反转而夸大；必须回到源稿事实。",
    },
    "trend-judgment": {
        "label": "趋势判断型",
        "slug": "trend-judgment",
        "opening_rule": "从一个市场、工具、平台或用户行为的变化切入。",
        "structure_rule": "发生了什么变化 -> 旧玩法为什么失效 -> 新标准 -> 谁会受益 -> 行动建议 -> 下一阶段选择。",
        "hook_rule": "把转化承接放在行动建议或下一阶段选择里。",
        "best_for": "行业变化、工具升级、市场洗牌、平台策略类文章。",
        "avoid": "不要写成空泛趋势评论；必须保留可执行建议。",
    },
    "decision-comparison": {
        "label": "路径选择型",
        "slug": "decision-comparison",
        "opening_rule": "从读者面前的两到三条选择路径切入。",
        "structure_rule": "选择分叉 -> 每条路径的成本/收益/风险 -> 排除错误路径 -> 推荐优先级 -> 下一步行动。",
        "hook_rule": "把转化承接放在推荐路径的执行条件里。",
        "best_for": "入局判断、工具选择、预算决策、是否扩产、是否报名/购买等选择题文章。",
        "avoid": "不要写成简单对比表；必须推动读者做出更清晰的行动选择。",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize a local variant rewrite workspace for a filesystem main article."
    )
    parser.add_argument(
        "--article-dir",
        help="Article directory such as main/260505/260505_1. Must contain main.md and metadata.json.",
    )
    parser.add_argument(
        "--angle",
        action="append",
        default=[],
        help="Narrative angle/template label. Repeat this flag for multiple variants.",
    )
    parser.add_argument(
        "--angles-file",
        help="Optional UTF-8 text file with one narrative angle label per line.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=6,
        help="Number of default narrative angles to use when --angle is omitted. Default: 6.",
    )
    parser.add_argument(
        "--list-angles",
        action="store_true",
        help="List built-in angle templates and exit.",
    )
    parser.add_argument(
        "--audience",
        action="append",
        default=[],
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--audiences-file",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--source",
        choices=["auto", "main", "artwork"],
        default="auto",
        help="Source article to rewrite. Default auto prefers artwork/output/main.md when present.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow resetting an existing variants workspace.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_workspace(path: Path, force: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not force:
            raise SystemExit(f"Variants workspace already exists and is not empty: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "angle"


def normalize_angle_labels(
    values: list[str],
    angles_file: str | None,
    count: int,
    legacy_values: list[str] | None = None,
    legacy_file: str | None = None,
) -> list[str]:
    raw_items: list[str] = []
    for value in values:
        raw_items.extend(re.split(r"[\n,，]+", value))
    if angles_file:
        raw_items.extend(Path(angles_file).read_text(encoding="utf-8").splitlines())
    for value in legacy_values or []:
        raw_items.extend(re.split(r"[\n,，]+", value))
    if legacy_file:
        raw_items.extend(Path(legacy_file).read_text(encoding="utf-8").splitlines())

    if not raw_items:
        if count < 1:
            raise SystemExit("--count must be at least 1.")
        selected = DEFAULT_ANGLE_KEYS[: min(count, len(DEFAULT_ANGLE_KEYS))]
        labels = [ANGLE_TEMPLATES[key]["label"] for key in selected]
        for index in range(len(labels) + 1, count + 1):
            labels.append(f"扩展叙事型{index:02d}")
        return labels

    seen: set[str] = set()
    angles: list[str] = []
    for item in raw_items:
        angle = item.strip()
        if not angle or angle in seen:
            continue
        seen.add(angle)
        angles.append(angle)

    if not angles:
        raise SystemExit("At least one angle is required.")
    return angles


def unique_slugs(labels: list[str]) -> dict[str, str]:
    counts: dict[str, int] = {}
    result: dict[str, str] = {}
    for label in labels:
        built_in = angle_template_for(label)
        base = built_in["slug"] if built_in else slugify(label)
        count = counts.get(base, 0) + 1
        counts[base] = count
        result[label] = base if count == 1 else f"{base}-{count}"
    return result


def angle_template_for(label: str) -> dict[str, str] | None:
    normalized = label.strip().lower()
    slug = slugify(label)
    for key, template in ANGLE_TEMPLATES.items():
        if normalized in {key.lower(), template["label"].lower()} or slug == template["slug"]:
            return dict(template)
    return None


def angle_plan_item(label: str, slug: str) -> dict[str, str]:
    template = angle_template_for(label)
    if template is None:
        template = {
            "label": label,
            "slug": slug,
            "opening_rule": "使用与其他变体不同的开头方式。",
            "structure_rule": "重排热点、痛点、解决方案和转化承接的出现顺序，避免沿用源文段落骨架。",
            "hook_rule": "保留源稿转化信息，但改变嵌入位置和承接方式。",
            "best_for": "用户指定的自定义叙事角度。",
            "avoid": "不要复用源文连续段落或其他变体的结构锚点。",
        }
    template["label"] = label
    template["slug"] = slug
    return template


def output_id_from(article_dir: Path, metadata: dict[str, Any]) -> str:
    output_id = metadata.get("output_id")
    if isinstance(output_id, str) and output_id.strip():
        return output_id.strip()
    return article_dir.name


def article_field(metadata: dict[str, Any], key: str) -> Any:
    article = metadata.get("article")
    if isinstance(article, dict):
        return article.get(key)
    return None


def resolve_source(article_dir: Path, source: str) -> tuple[Path, Path]:
    base_main = article_dir / "main.md"
    base_metadata = article_dir / "metadata.json"
    artwork_main = article_dir / "artwork" / "output" / "main.md"
    artwork_metadata = article_dir / "artwork" / "output" / "metadata.json"

    if source == "artwork":
        if not artwork_main.exists():
            raise SystemExit(f"Missing artwork output article: {artwork_main}")
        return artwork_main, artwork_metadata if artwork_metadata.exists() else base_metadata
    if source == "main":
        return base_main, base_metadata
    if artwork_main.exists():
        return artwork_main, artwork_metadata if artwork_metadata.exists() else base_metadata
    return base_main, base_metadata


def metadata_template(
    source_metadata: dict[str, Any],
    output_id: str,
    angle_label: str,
    source_main: Path,
) -> str:
    tags = article_field(source_metadata, "tags")
    if not isinstance(tags, list):
        tags = []
    payload = {
        "input_mode": "filesystem",
        "output_id": output_id,
        "audience_label": angle_label,
        "angle_label": angle_label,
        "article": {
            "role": "variant",
            "file": "others.md",
            "title": "",
            "summary": "",
            "tags": tags,
            "search_intents": [],
            "based_on_output_id": output_id,
            "source_main_file": source_main.as_posix(),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_batch_task(
    article_dir: Path,
    variants_dir: Path,
    output_id: str,
    source_main: Path,
    source_metadata: Path,
    title: str,
    summary: str,
    angles: list[str],
) -> str:
    angle_lines = "\n".join(f"- {angle}" for angle in angles)
    return f"""# 变体批量改写任务

输入信息：

- input_mode: filesystem
- output_id: {output_id}
- article_dir: {article_dir.as_posix()}
- source_main: {source_main.as_posix()}
- source_metadata: {source_metadata.as_posix()}
- title: {title or "未填写"}
- summary: {summary or "未填写"}

目标叙事模板：

{angle_lines}

执行要求：

1. 先完善 `invariant_brief.md`，明确热点、痛点、解决方案、下一步行动和 must_keep。
   必须先区分资产层与解释层：提示词、代码块、参数、模板、图片、链接、促销/联系方式属于资产层；开头、过渡、解释、总结属于解释层。
2. 按上方顺序串行处理叙事模板，一次只完成一个模板。
3. 每个模板目录下先阅读 `task.md`、`manifest.json`、`source_article.md`、`metadata.template.json`、`../invariant_brief.md`、`../angle_plan.json`。
4. 每个模板必须分配给独立 subagent。
5. 每个 subagent 必须调用 `wechat-main-variant-rewriter`，并只在自己的 `output/` 目录写入 `others.md` 和 `metadata.json`。
6. 父 agent 不得直接编写初始正文；父 agent 只能初始化任务、提炼 brief、协调、审稿、相似度检查，以及在 subagent 结果不合格时做修正。
7. 变体必须保留源稿里的全部事实、营销/推广信息和图片 Markdown/图片占位。
   对提示词、代码、参数、模板、清单等可复制资产，默认完整保留，不要摘要化、语义替换或为了降低重复度而删减。
8. 叙事结构必须明显变化：开头方式、段落顺序、论证路径、转化承接位置不能照搬源文或其他变体。
9. 正文里不要直说“本文采用某某模板”，也不要出现 `source_article`、`源文`、`源稿`、`原文`、`改写`、`变体`、`叙事模板`、`钩子`、`hook` 等内部工作词。
10. 写完每个模板后运行：
   `python3 .agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py --run-dir <angle-dir>`
11. 当前模板校验通过后，再开始下一个模板。
12. 全部完成后运行：
   `python3 .agents/skills/wechat-main-variant-batch-rewriter/scripts/check_variant_similarity.py --variants-dir {variants_dir.as_posix()}`

最终输出根目录：`{variants_dir.as_posix()}`
"""


def render_invariant_brief(title: str, summary: str, source_main: Path, source_article: str) -> str:
    image_count = len(re.findall(r"!\[[^\]]*\]\([^)]+\)|<img\b", source_article, flags=re.IGNORECASE))
    link_count = len(re.findall(r"\[[^\]]+\]\([^)]+\)", source_article))
    return f"""# Invariant Brief

This file is a planning brief for all variants. The parent agent should refine it before spawning subagents.

## Source

- source_main: {source_main.as_posix()}
- title: {title or "未填写"}
- summary: {summary or "未填写"}
- image_count: {image_count}
- markdown_link_count: {link_count}

## Required Invariants

- hotspot: TODO - the timely event, trend, release, or trigger
- pain: TODO - the reader problem, failure mode, cost, or confusion
- solution: TODO - the recommended method, product path, judgment standard, or workflow
- next_action: TODO - the conversion or retention element, such as coupon, tutorial, service, product link, customer service, or next action

## Asset Blocks

Classify copyable or executable source assets here before rewriting. Preserve these with high fidelity in every variant.

- fenced_code_blocks: TODO - if the source contains prompts, code, commands, parameters, or templates in fenced blocks, keep every block unless the user explicitly asks to remove one
- prompts_or_templates: TODO - full prompts, prompt chains, reusable templates, checklists, tables, commands, or configuration values that readers are expected to copy
- media_and_links: TODO - image Markdown, source links, tutorial links, product links, QR codes, contact methods
- promotional_blocks: TODO - coupon, service, price, quota, customer-service, or conversion copy that must survive
- fixed_claims: TODO - names, dates, capabilities, constraints, or factual claims that must not be invented or weakened

- Preserve every source fact that supports the hotspot, pain, solution, or next action.
- Preserve all image Markdown / image placeholders.
- Preserve all promotional blocks, links, prices, contact methods, coupons, tutorials, and service claims from the source.
- Do not invent prices, capabilities, dates, promises, or source claims.
- Do not summarize, paraphrase, or remove asset blocks to reduce similarity.

## Rewrite Zones

Rewrite these areas to create meaningful variants:

- opening angle, reader problem setup, case framing, section titles, transitions, explanations, usage guidance, risk reminders, conclusion, and conversion placement
- semantic rewriting is encouraged here, as long as source facts and asset blocks remain intact

## Similarity Guardrails

- Keep the invariants; do not keep the source skeleton.
- Change opening style, section order, argument order, and conversion placement across variants.
- Avoid exact repeated explanatory paragraphs except asset blocks, mandatory links, images, coupon text, and contact blocks.
- If high similarity is caused by fenced prompts/code/templates or fixed promotional/media assets, preserve the assets and vary only the surrounding prose.
"""


def render_angle_task(
    output_id: str,
    angle: dict[str, str],
    source_main: Path,
    source_metadata: Path,
    output_dir: Path,
) -> str:
    label = angle["label"]
    return f"""# 单个叙事模板变体改写任务

输入信息：

- input_mode: filesystem
- output_id: {output_id}
- angle_label: {label}
- compatibility_audience_label: {label}
- source_main: {source_main.as_posix()}
- source_metadata: {source_metadata.as_posix()}

请先阅读：

- `source_article.md`
- `manifest.json`
- `metadata.template.json`
- `../invariant_brief.md`
- `../angle_plan.json`

然后在输出目录中产出：

- `others.md`
- `metadata.json`

叙事模板：

- opening_rule: {angle["opening_rule"]}
- structure_rule: {angle["structure_rule"]}
- hook_rule: {angle["hook_rule"]}
- best_for: {angle["best_for"]}
- avoid: {angle["avoid"]}

要求：

- 以 `source_article.md` 为事实锚点，不编造源稿没有的事实、价格、能力、数据或承诺
- 以 `../invariant_brief.md` 为不变量锚点，保留热点、痛点、解决方案、下一步行动和 must_keep
- 先执行内容分层：提示词、代码块、参数、模板、图片、链接、促销/联系方式是资产层；开头、过渡、解释、总结是解释层
- 资产层必须高保真保留；如果源文有 fenced code block、完整提示词、命令、参数或模板，输出中不得减少这些块，也不要为了降低重复度进行摘要化或相近语义替换
- 重复度控制只作用于解释层：可以重写开头、案例解释、过渡、标题、风险提示、使用建议和结尾承接
- 原文中的营销/推广信息必须全部保留，并结合本文结构自然嵌入，不能删除、硬切，不能比原文少
- 原文中的图片 Markdown 或图片占位必须全部保留，不能缺少任何一张
- 必须重构文章结构：开头方式、段落顺序、论证路径、转化承接位置都要服务当前叙事模板
- 不要沿用源文段落骨架；不要连续复用源文长段落；不要复用其他变体的固定开头和小标题
- 正文里不要直说“本文采用{label}”，也不要出现 `source_article`、`源文`、`源稿`、`原文`、`改写`、`变体`、`叙事模板`、`钩子`、`hook` 等内部工作词
- `metadata.json` 从 `metadata.template.json` 开始填写
- `metadata.json.article.search_intents` 必须填写当前变体实际承接的搜索入口；优先从主稿 metadata、相关 material 的 `搜索入口` 或 wiki/search-intents 中选择。不要把主稿全部关键词复制进每个变体
- 按叙事模板分配入口：问题诊断型优先痛点/问题排查，方法论拆解型优先教程，路径选择型优先对比/值不值，趋势判断型优先趋势观点
- `metadata.json.audience_label` 保持为 `{label}`，这是为了兼容现有校验脚本
- `others.md` 应该是一篇完整公众号成稿，不是摘要、改写说明或任务记录
- 写到完整、有用即可，不要为了满足固定字数而注水
- 写完后执行：
  `python3 .agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py --run-dir {output_dir.parent.as_posix()}`

输出目录：`{output_dir.as_posix()}`
"""


def angle_manifest(
    article_dir: Path,
    variant_dir: Path,
    output_id: str,
    angle: dict[str, str],
    slug: str,
    source_main: Path,
    source_metadata: Path,
) -> dict[str, Any]:
    label = angle["label"]
    return {
        "skill": "wechat-main-variant-rewriter",
        "input_mode": "filesystem",
        "output_id": output_id,
        "audience_label": label,
        "angle_label": label,
        "angle_slug": slug,
        "angle": angle,
        "article_dir": article_dir.as_posix(),
        "variant_dir": variant_dir.as_posix(),
        "output_dir": (variant_dir / "output").as_posix(),
        "source_main": source_main.as_posix(),
        "source_metadata": source_metadata.as_posix(),
        "expected_outputs": ["others.md", "metadata.json"],
        "validation_script": ".agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py",
    }


def main() -> int:
    args = parse_args()
    if args.list_angles:
        for key in DEFAULT_ANGLE_KEYS:
            template = ANGLE_TEMPLATES[key]
            print(f"{template['label']}\t{template['slug']}\t{template['best_for']}")
        return 0

    if not args.article_dir:
        raise SystemExit("--article-dir is required unless --list-angles is used.")

    article_dir = Path(args.article_dir)
    base_main = article_dir / "main.md"
    base_metadata = article_dir / "metadata.json"
    if not article_dir.is_dir():
        raise SystemExit(f"Article directory not found: {article_dir}")
    if not base_main.exists():
        raise SystemExit(f"Missing article file: {base_main}")
    if not base_metadata.exists():
        raise SystemExit(f"Missing metadata file: {base_metadata}")

    base_metadata_payload = read_json(base_metadata)
    output_id = output_id_from(article_dir, base_metadata_payload)
    source_main, source_metadata = resolve_source(article_dir, args.source)
    source_metadata_payload = read_json(source_metadata)
    source_article = source_main.read_text(encoding="utf-8")
    angles = normalize_angle_labels(
        args.angle,
        args.angles_file,
        args.count,
        legacy_values=args.audience,
        legacy_file=args.audiences_file,
    )
    slugs = unique_slugs(angles)
    angle_plan = [angle_plan_item(angle, slugs[angle]) for angle in angles]

    variants_dir = article_dir / "variants"
    ensure_workspace(variants_dir, args.force)

    title = str(article_field(source_metadata_payload, "title") or "")
    summary = str(article_field(source_metadata_payload, "summary") or "")

    batch_manifest = {
        "skill": "wechat-main-variant-batch-rewriter",
        "input_mode": "filesystem",
        "output_id": output_id,
        "article_dir": article_dir.as_posix(),
        "variants_dir": variants_dir.as_posix(),
        "source_main": source_main.as_posix(),
        "source_metadata": source_metadata.as_posix(),
        "mode": "angle",
        "angles": [
            {
                "label": angle["label"],
                "slug": angle["slug"],
                "variant_dir": (variants_dir / angle["slug"]).as_posix(),
                "output_dir": (variants_dir / angle["slug"] / "output").as_posix(),
                "structure_rule": angle["structure_rule"],
            }
            for angle in angle_plan
        ],
        "expected_outputs": ["<angle>/output/others.md", "<angle>/output/metadata.json"],
        "soft_validation": {
            "similarity_script": ".agents/skills/wechat-main-variant-batch-rewriter/scripts/check_variant_similarity.py",
            "recommended_command": f"python3 .agents/skills/wechat-main-variant-batch-rewriter/scripts/check_variant_similarity.py --variants-dir {variants_dir.as_posix()}",
        },
    }
    write_text(
        variants_dir / "task.md",
        render_batch_task(
            article_dir,
            variants_dir,
            output_id,
            source_main,
            source_metadata,
            title,
            summary,
            angles,
        ),
    )
    write_text(
        variants_dir / "manifest.json",
        json.dumps(batch_manifest, ensure_ascii=False, indent=2),
    )
    write_text(
        variants_dir / "invariant_brief.md",
        render_invariant_brief(title, summary, source_main, source_article),
    )
    write_text(
        variants_dir / "angle_plan.json",
        json.dumps(angle_plan, ensure_ascii=False, indent=2),
    )

    for angle in angle_plan:
        label = angle["label"]
        slug = angle["slug"]
        variant_dir = variants_dir / slug
        output_dir = variant_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        write_text(
            variant_dir / "task.md",
            render_angle_task(output_id, angle, source_main, source_metadata, output_dir),
        )
        write_text(variant_dir / "source_article.md", source_article)
        write_text(
            variant_dir / "manifest.json",
            json.dumps(
                angle_manifest(
                    article_dir,
                    variant_dir,
                    output_id,
                    angle,
                    slug,
                    source_main,
                    source_metadata,
                ),
                ensure_ascii=False,
                indent=2,
            ),
        )
        write_text(
            variant_dir / "metadata.template.json",
            metadata_template(source_metadata_payload, output_id, label, source_main),
        )

    print(f"Variants directory: {variants_dir}")
    for angle in angle_plan:
        print(f"- {angle['label']}: {variants_dir / angle['slug'] / 'output'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
