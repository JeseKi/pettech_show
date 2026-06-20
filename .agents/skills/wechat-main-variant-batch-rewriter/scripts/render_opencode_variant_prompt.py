#!/usr/bin/env python3
"""Render one opencode prompt for a chunk of variant rewrite angles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "deepseek/deepseek-v4-pro"
DEFAULT_MAX_VARIANTS = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants-dir", required=True, help="variants/ workspace from init_variant_batch.py")
    parser.add_argument("--session-index", type=int, required=True, help="1-based opencode session index")
    parser.add_argument("--start", type=int, required=True, help="0-based first angle index for this chunk")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_MAX_VARIANTS,
        help=f"Maximum variants in this prompt. Default {DEFAULT_MAX_VARIANTS}.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model recorded in prompt. Default {DEFAULT_MODEL}.")
    parser.add_argument("--out", help="Prompt output path. Defaults under variants/opencode/prompts/")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def angle_rows(variants_dir: Path, angles: list[dict[str, Any]]) -> str:
    rows = []
    for index, angle in enumerate(angles, start=1):
        label = angle["label"]
        slug = angle["slug"]
        run_dir = variants_dir / slug
        rows.append(
            "\n".join(
                [
                    f"{index}. {label}",
                    f"   - slug: {slug}",
                    f"   - run_dir: {run_dir.as_posix()}",
                    f"   - output_dir: {(run_dir / 'output').as_posix()}",
                    f"   - structure_rule: {angle.get('structure_rule', '')}",
                ]
            )
        )
    return "\n".join(rows)


def render(variants_dir: Path, session_index: int, start: int, limit: int, model: str) -> str:
    manifest = load_json(variants_dir / "manifest.json")
    angle_plan = load_json(variants_dir / "angle_plan.json")
    if not isinstance(angle_plan, list):
        raise SystemExit(f"angle_plan.json must contain a list: {variants_dir / 'angle_plan.json'}")
    if limit < 1 or limit > DEFAULT_MAX_VARIANTS:
        raise SystemExit(f"--limit must be between 1 and {DEFAULT_MAX_VARIANTS}")
    selected = angle_plan[start : start + limit]
    if not selected:
        raise SystemExit("Selected angle chunk is empty")

    article_dir = manifest.get("article_dir", "")
    source_main = manifest.get("source_main", "")
    source_metadata = manifest.get("source_metadata", "")
    return f"""你是 opencode 变体批量写作 sub agent。

模型：{model}
会话编号：{session_index}
一次会话最多负责 {DEFAULT_MAX_VARIANTS} 篇变体；本次负责 {len(selected)} 篇。

硬边界：
- 只处理下方列出的 run_dir。
- 只写每个 run_dir 的 `output/others.md` 和 `output/metadata.json`，以及必要的轻量进度文件。
- 不要修改主稿、其他变体目录、批次计划、图片、KiVault 文件或标题文件。
- 不要调用 Codex、不要创建更深层 subagent。
- 不要调用 Codex conversation thread, heartbeat, 或 automation tools，包括但不限于 codex_app.create_thread, codex_app.send_message_to_thread, codex_app.automation_update, codex_app.list_threads, codex_app.read_thread。
- 不要上传文件，不要调用 KiVault。

上下文入口：
- article_dir: {article_dir}
- variants_dir: {variants_dir.as_posix()}
- source_main: {source_main}
- source_metadata: {source_metadata}
- invariant_brief: {(variants_dir / 'invariant_brief.md').as_posix()}
- angle_plan: {(variants_dir / 'angle_plan.json').as_posix()}
- style_reference: .agents/skills/wechat-daily-writer/references/style_reference.md
- single_variant_skill: .agents/skills/wechat-main-variant-rewriter/SKILL.md

本次负责的变体：

{angle_rows(variants_dir, selected)}

工作流程：
1. 先阅读 `invariant_brief.md`、`angle_plan.json`、style reference、single variant skill。
2. 对本次列出的每个 run_dir，阅读：
   - `task.md`
   - `manifest.json`
   - `source_article.md`
   - `metadata.template.json`
3. 在一个 opencode 上下文中依次写完本次所有变体，利用共享上下文和缓存，但每篇必须结构明显不同。
4. 每个变体输出：
   - `output/others.md`
   - `output/metadata.json`
5. 每写完一篇，立即运行：
   `python3 .agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py --run-dir <run_dir>`
6. 如果校验失败，修正该 run_dir 的输出并重新校验，直到通过或明确失败原因。
7. 全部完成后，输出每个 run_dir 的状态和文件路径。

写作要求：
- 以 `source_article.md` 为事实锚点，不编造源稿没有的事实、价格、能力、数据或承诺。
- 保留所有图片 Markdown、链接、促销/联系方式、价格、领取方式、教程入口、服务承接信息。
- 如果源文有 fenced code block、完整提示词、命令、参数、模板、表格或清单，默认高保真保留，不能为了降重而删减。
- 相似度控制主要作用于开头、结构顺序、小标题、解释段、过渡、案例框架、结尾承接。
- 正文不要出现内部工作词：source_article、源文、源稿、原文、改写、变体、叙事模板、hook、钩子。
- `metadata.json` 必须从 `metadata.template.json` 延展，保留 `audience_label` 兼容字段，并填写非空 title/summary/tags。
- `metadata.json.article.search_intents` 必须填写当前变体实际承接的搜索入口；优先从主稿 metadata、相关 material 的 `搜索入口` 或 wiki/search-intents 中选择。不要把主稿全部关键词复制进每个变体。
- 按叙事模板分配入口：问题诊断型优先痛点/问题排查，方法论拆解型优先教程，路径选择型优先对比/值不值，趋势判断型优先趋势观点。

完成后停止，不要继续处理未分配给本 session 的变体。
"""


def main() -> int:
    args = parse_args()
    variants_dir = Path(args.variants_dir)
    if not variants_dir.is_dir():
        raise SystemExit(f"Variants directory not found: {variants_dir}")
    prompt = render(variants_dir, args.session_index, args.start, args.limit, args.model)
    out = Path(args.out) if args.out else variants_dir / "opencode" / "prompts" / f"session-{args.session_index:02d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prompt, encoding="utf-8")
    print(out.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
