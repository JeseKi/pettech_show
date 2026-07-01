# -*- coding: utf-8 -*-
"""OpenCode runner and prompt construction for social card jobs."""

from __future__ import annotations

from pathlib import Path

from src.server.opencode import run_opencode_in_tmux


def run_opencode(workdir: Path, *, post_count: int, cards_per_post: int) -> None:
    _run_opencode_with_prompt(
        workdir,
        title="Xiaohongshu social card generation",
        prompt=build_prompt(
            workdir,
            post_count=post_count,
            cards_per_post=cards_per_post,
        ),
    )


def _run_opencode_with_prompt(workdir: Path, *, title: str, prompt: str) -> None:
    run_opencode_in_tmux(workdir, title=title, prompt=prompt)


def build_prompt(workdir: Path, *, post_count: int, cards_per_post: int) -> str:
    variant_count = max(0, post_count - 1)
    total_card_count = post_count * cards_per_post
    return f"""
你在一个隔离的小红书图文卡生成工作目录中工作：{workdir.as_posix()}

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
- 所有图文卡生成、渲染和校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

目标：
0. 机器可读参数：
   - post_count: {post_count}
   - cards_per_post: {cards_per_post}
   - total_card_count: {total_card_count}
1. 读取 `source/main.md` 和 `source/metadata.json`，使用 $guizang-social-card-skill 生成 {post_count} 篇 Xiaohongshu/Rednote 图文；每篇图文包含 {cards_per_post} 张 3:4 图文卡。
2. 输出目录必须是当前目录下的 `xhs_guizang/`，不要写入源 Daily Writer 工作区。
3. 第 1 篇图文输出到 `xhs_guizang/`；如果 post_count 大于 1，额外 {variant_count} 篇必须输出到 `xhs_guizang_variants/variant-01/`、`xhs_guizang_variants/variant-02/` 这类目录。
4. 每篇图文必须是基于同一篇源文章的不同小红书发布角度，不能只是改颜色或重复排版。可从不同 hook、受众场景、痛点入口、方法论结构、避坑清单中拆出差异。
5. 每个图文目录都必须保留：
   - `index.html`
   - `manifest.json`
   - `plan.md` 或 `prompts.md`
   - `output/*.png`
   - `main.md`
   对变体目录同理，例如 `xhs_guizang_variants/variant-01/index.html`、`xhs_guizang_variants/variant-01/main.md`。
6. 每个 `index.html` 必须支持 `?card=0` 到 `?card={cards_per_post - 1}`，每次只渲染一张 1080x1440 的图文卡，便于本地截图。
7. 每个图文目录的 `manifest.json` 必须列出 {cards_per_post} 张 PNG 输出路径，可使用 `cards[*].file`、`cards[*].path`、`cards[*].output` 或 `uploaded_images[*].file`。
8. 使用当前目录已提供的本地渲染脚本生成 PNG：
   - 第 1 篇运行：`node tools/render_social_deck.mjs xhs_guizang --count {cards_per_post}`
   - 变体运行：`node tools/render_social_deck.mjs xhs_guizang_variants/variant-01 --count {cards_per_post}`，依次类推。
   该脚本直接使用本机 Chrome/Chromium headless 截图，不依赖 Playwright，也不需要 npm install。
9. 每个图文目录的 `output/` 下必须正好有 {cards_per_post} 张 PNG 图文卡。全部目录合计必须正好有 {total_card_count} 张 PNG。
10. 每个 `main.md` 应按顺序引用本地图文卡图片，使用相对于该图文目录的路径，例如 `output/xhs-01-cover.png`。
11. 完成后直接结束，不要等待用户继续输入。

要求：
- 不要修改 `source/main.md` 和 `source/metadata.json`。
- 不要访问、修改或重置任何 Daily Writer 任务的 `progress.json`、`main.md`、`metadata.json`、`artwork/` 或 `variants/`。
- 不要上传图片到 KiVault 或任何云服务。
- 不要使用旧的 `xhs_carousel_imagegen` 直出图片流程。
- 不要使用 imagegen、grsai-image-generator 或任何云端图片生成服务。
- 不要 import `playwright`、`puppeteer` 或其他当前目录没有安装的浏览器自动化包；不要运行 `npm install`。渲染 PNG 只能使用 `tools/render_social_deck.mjs` 或同等的本机 Chrome/Chromium CLI 截图方式。
- 字体优先使用当前工作目录内 `.agents/assets/fonts/` 下的已授权字体文件，例如 `msyh.ttc`、`msyh.ttf`、`msyhbd.ttc` 或 `MicrosoftYaHei.ttf`；生成 `index.html` 时可通过 `@font-face` 引用这些本地字体，并把中文字体族放在 `font-family` 首位。
- 不要递归 Glob `/usr/share/fonts` 或任何系统字体目录；如需系统字体，只能用 CSS 系统字体 fallback 或 `fc-match`/`fc-list` 查询到的单个字体路径。
- 如果需要图源，可按 guizang skill 的 Web-Sourced Images 流程自行查找并记录到 `xhs_guizang/assets/SOURCES.md`。
- 如果图文卡生成失败，必须在当前目录的 `progress.json` 和日志中写清楚失败原因。
""".strip()
