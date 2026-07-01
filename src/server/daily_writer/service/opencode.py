# -*- coding: utf-8 -*-
"""OpenCode runner and prompt construction for daily writer jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.server.opencode import run_opencode_in_tmux


def run_opencode(workdir: Path, params: dict[str, Any], row: dict[str, str]) -> None:
    _run_opencode_with_prompt(
        workdir,
        title="Daily writer generation",
        prompt=build_prompt(workdir, params, row),
    )


def run_variant_opencode(
    workdir: Path,
    *,
    article_dir: str,
    variant_count: int,
) -> None:
    _run_opencode_with_prompt(
        workdir,
        title="Long article variant generation",
        prompt=build_variant_prompt(
            workdir,
            article_dir=article_dir,
            variant_count=variant_count,
        ),
    )


def run_artwork_opencode(
    workdir: Path,
    *,
    article_dir: str,
) -> None:
    _run_opencode_with_prompt(
        workdir,
        title="Long article artwork generation",
        prompt=build_artwork_prompt(workdir, article_dir=article_dir),
    )


def run_repair_opencode(workdir: Path, *, error: str, article_dir: str | None = None) -> None:
    _run_opencode_with_prompt(
        workdir,
        title="Daily writer JSON repair",
        prompt=build_repair_prompt(workdir, error=error, article_dir=article_dir),
    )


def _run_opencode_with_prompt(workdir: Path, *, title: str, prompt: str) -> None:
    run_opencode_in_tmux(workdir, title=title, prompt=prompt, session_key=title)


def build_prompt(workdir: Path, params: dict[str, Any], row: dict[str, str]) -> str:
    output_date = params.get("output_date") or ""
    output_date_line = (
        f"- 本次明确指定 output_date: {output_date}，必须按该日期生成 main/<output_date>/<output_id>/。"
        if output_date
        else "- 未指定 output_date，按 skill 规则使用今天当前日期的 YYMMDD。"
    )
    row_json = json.dumps(row, ensure_ascii=False, indent=2)
    return f"""
你在一个隔离的长文生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`；`event`、`step` 的值必须使用中文。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件；所有 Skill 和子 Agent 都禁止清空、重置或重建已有 `events`。
- `event` 只能使用 `开始`、`完成` 或 `失败`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `开始` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的中文步骤名。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `完成` 事件，`summary` 简要概括刚完成的内容。
- 如果任务失败，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 所有长文生成和 metadata JSON 校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

目标：
1. 使用 $wechat-daily-writer，从当前目录的 `wiki/`、`material/`、`raw/` 生成一篇长文。
2. 必须把下面选中的选题矩阵行作为本次生产字段来源；其中 topic、pain_point、solution、hook 若非空，必须按 skill 规则原样写入 metadata 顶层字段。
3. 当前目录下 `input/selected_seed_row.json` 也保存了同一行数据，可读取使用。
4. {output_date_line}
5. 输出必须是 `main/<output_date>/<output_id>/main.md` 和 `main/<output_date>/<output_id>/metadata.json`。
6. 完成后必须运行：
   python3 .agents/skills/wechat-daily-writer/scripts/check_article_json.py
7. 校验通过后直接结束，不要等待用户继续输入。

选中的选题矩阵行：
```json
{row_json}
```

要求：
- 不要覆盖当前目录外的任何文件。
- 不要重新生成 AI Wiki 或选题矩阵，只使用已存在的 wiki/material/raw 资产。
- main.md 必须是纯文本 Markdown，不允许图片语法、HTML 图片、图片占位、封面图块、二维码块或图片链接。
- 正文不要出现素材、材料、metadata、raw、本地文件、提示词等内部整理口吻。
- metadata.json 必须符合 wechat-daily-writer 的输出契约。
""".strip()


def build_variant_prompt(workdir: Path, *, article_dir: str, variant_count: int) -> str:
    variants_dir = f"{article_dir}/variants"
    return f"""
你在一个隔离的长文变体生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`；`event`、`step` 的值必须使用中文。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件；所有 Skill 和子 Agent 都禁止清空、重置或重建已有 `events`。
- `event` 只能使用 `开始`、`完成` 或 `失败`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `开始` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的中文步骤名。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `完成` 事件，`summary` 简要概括刚完成的内容。
- 如果任务失败，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 所有变体生成和 metadata JSON 校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

目标：
1. 使用 $wechat-main-variant-batch-rewriter，为 `{article_dir}` 生成 {variant_count} 篇结构明显不同的长文变体。
2. 初始化工作区时必须使用：
   python3 .agents/skills/wechat-main-variant-batch-rewriter/scripts/init_variant_batch.py --article-dir {article_dir} --count {variant_count} --source main
3. 生成变体时必须使用 batch skill 默认流程，并保证每个变体写入：
   `{variants_dir}/<angle-slug>/output/others.md`
   `{variants_dir}/<angle-slug>/output/metadata.json`
4. 变体完成后运行：
   python3 .agents/skills/wechat-daily-writer/scripts/check_article_json.py --article-dir {article_dir} --include-variants
5. 校验通过后直接结束，不要等待用户继续输入。

要求：
- 不要修改 `{article_dir}/main.md` 和 `{article_dir}/metadata.json`。
- 不要覆盖当前目录外的任何文件。
- 如果某个变体失败，必须在 progress.json 和日志中写清楚失败原因。
- 输出目录必须是 `{variants_dir}/`。
""".strip()


def build_artwork_prompt(workdir: Path, *, article_dir: str) -> str:
    return f"""
你在一个隔离的长文封面和插图生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`；`event`、`step` 的值必须使用中文。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件；所有 Skill 和子 Agent 都禁止清空、重置或重建已有 `events`。
- `event` 只能使用 `开始`、`完成` 或 `失败`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `开始` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的中文步骤名。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `完成` 事件，`summary` 简要概括刚完成的内容。
- 如果任务失败，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 所有封面和插图生成、校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

目标：
1. 使用 $wechat-main-artwork-coordinator，为 `{article_dir}` 生成本地封面和正文插图。
2. 初始化工作区时必须使用：
   python3 .agents/skills/wechat-main-artwork-coordinator/scripts/init_artwork.py --article-dir {article_dir}
3. 必须使用 $guizang-social-card-skill 生成视觉卡片。
4. 必须运行：
   python3 .agents/skills/wechat-main-artwork-coordinator/scripts/prepare_upload_images.py --article-dir {article_dir}
5. 必须产出至少 1 张封面图和至少 1 张正文插图。
6. 完成后直接结束，不要等待用户继续输入。

要求：
- 不要修改 `{article_dir}/main.md` 和 `{article_dir}/metadata.json`。
- 不要覆盖当前目录外的任何文件。
- 不要上传图片到 KiVault 或任何云服务。
- 不要使用 imagegen、grsai-image-generator 或任何云端图片生成服务。
- 不要在临时渲染脚本里从 `.agents/skills/guizang-social-card-skill/node_modules/playwright/index.js` 做相对路径 import。
- 如果需要用浏览器截图 HTML，优先使用系统 Chromium：读取 `CHROME_BIN` 或 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`，否则尝试 `/usr/bin/chromium`、`/usr/bin/chromium-browser`、`/usr/bin/google-chrome`；不要依赖 `/root/.cache/ms-playwright/` 中的浏览器缓存。
- 如果使用 Playwright 包，必须用默认导入兼容 CommonJS：`import playwright from "playwright"; const {{ chromium }} = playwright;`，并在 `chromium.launch()` 中传入上述 `executablePath`。
- 字体优先使用当前工作目录内 `.agents/assets/fonts/` 下的已授权字体文件，例如 `msyh.ttc`、`msyh.ttf`、`msyhbd.ttc` 或 `MicrosoftYaHei.ttf`；如果目录不存在或没有可用字体，再使用 CSS 系统字体 fallback。
- 不要递归 Glob `/usr/share/fonts` 或任何系统字体目录；如需系统字体，只能用 `fc-match`/`fc-list` 查询到的单个字体路径，查询失败时使用 Pillow 默认字体继续渲染。
- 如果浏览器不可用，可以改用本地 Python/Pillow 渲染，但必须保留 Guizang 的 `index.html`、`manifest.json`、`plan.md` 或 `prompts.md` 作为设计源文件。
- 图片最终必须保存在 `{article_dir}/artwork/cover/images/`、`{article_dir}/artwork/illustrations/images/` 或 `{article_dir}/artwork/upload_ready/` 下。
- 如果图片生成失败，必须在 progress.json 和日志中写清楚失败原因。
""".strip()


def build_repair_prompt(workdir: Path, *, error: str, article_dir: str | None = None) -> str:
    check_command = (
        f"python3 .agents/skills/wechat-daily-writer/scripts/check_article_json.py --article-dir {article_dir} --include-variants"
        if article_dir
        else "python3 .agents/skills/wechat-daily-writer/scripts/check_article_json.py"
    )
    scope = f"`{article_dir}` 及其 variants 下" if article_dir else "`main/` 下最新长文"
    return f"""
你在一个隔离的长文生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

后端在 AI 标记完成后执行 metadata JSON 校验失败，错误如下：
{error}

任务：
1. 修复 {scope} 的 metadata JSON 文件，重点确保每个 `metadata.json` 是严格合法 JSON object。
2. 不需要检查或改写 Markdown 正文。
3. 必须自行运行：
   {check_command}
4. 如果校验仍失败，继续修复并重跑，直到通过或明确失败原因。

进度协议：
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件；所有 Skill 和子 Agent 都禁止清空、重置或重建已有 `events`。
- `event`、`step` 的值必须使用中文；`event` 只能使用 `开始`、`完成` 或 `失败`。
- 修复开始时写入 `status: running`，`current_step: 修复 metadata JSON`，并追加 `开始` 事件。
- 校验通过后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。
- 如果无法修复，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件说明原因。
""".strip()
