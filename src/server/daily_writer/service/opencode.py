# -*- coding: utf-8 -*-
"""OpenCode runner and prompt construction for daily writer jobs."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.progress import progress_marked_complete
from src.server.config import global_config


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


def _run_opencode_with_prompt(workdir: Path, *, title: str, prompt: str) -> None:
    command = shlex.split(global_config.aiwiki_opencode_command)
    if not command:
        raise RuntimeError("AIWIKI_OPENCODE_COMMAND 不能为空")
    args = [
        *command,
        "run",
        "--dir",
        workdir.as_posix(),
        "--title",
        title,
    ]
    if global_config.aiwiki_opencode_model:
        args.extend(["--model", global_config.aiwiki_opencode_model])
    if global_config.aiwiki_opencode_agent:
        args.extend(["--agent", global_config.aiwiki_opencode_agent])
    if global_config.aiwiki_opencode_extra_args:
        args.extend(shlex.split(global_config.aiwiki_opencode_extra_args))
    args.append(prompt)

    log_path = workdir / "logs" / "opencode.log"
    append_log(workdir, "$ " + " ".join(shlex.quote(arg) for arg in args[:-1]) + " <prompt>")
    env = os.environ.copy()
    config_path = workdir / "config.json"
    if config_path.exists():
        env["OPENCODE_CONFIG"] = config_path.as_posix()
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            args,
            cwd=workdir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )
        deadline = datetime.now(timezone.utc).timestamp() + global_config.aiwiki_task_timeout_seconds
        while process.poll() is None:
            if datetime.now(timezone.utc).timestamp() > deadline:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                raise RuntimeError("OpenCode 执行超时")

            if progress_marked_complete(workdir):
                append_log(workdir, "progress.json 已标记任务完成，后端结束 OpenCode 并解析结果。")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                return

            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

        return_code = process.returncode
    if return_code != 0:
        raise RuntimeError(f"OpenCode 执行失败，退出码 {return_code}")


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
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`，其中 `event` 使用 `started`、`completed` 或 `failed`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `started` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的事。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `completed` 事件，`summary` 简要概括刚完成的内容。
- 所有长文生成和校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"completed","step":"all","summary":"任务完成"}}`。

目标：
1. 使用 $wechat-daily-writer，从当前目录的 `wiki/`、`material/`、`raw/` 生成一篇长文。
2. 必须把下面选中的选题矩阵行作为本次生产字段来源；其中 topic、pain_point、solution、hook 若非空，必须按 skill 规则原样写入 metadata 顶层字段。
3. 当前目录下 `input/selected_seed_row.json` 也保存了同一行数据，可读取使用。
4. {output_date_line}
5. 输出必须是 `main/<output_date>/<output_id>/main.md` 和 `main/<output_date>/<output_id>/metadata.json`。
6. 完成后直接结束，不要等待用户继续输入。

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
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`，其中 `event` 使用 `started`、`completed` 或 `failed`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `started` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的事。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `completed` 事件，`summary` 简要概括刚完成的内容。
- 所有变体生成、校验和相似度检查都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"completed","step":"all","summary":"任务完成"}}`。

目标：
1. 使用 $wechat-main-variant-batch-rewriter，为 `{article_dir}` 生成 {variant_count} 篇结构明显不同的长文变体。
2. 初始化工作区时必须使用：
   python3 .agents/skills/wechat-main-variant-batch-rewriter/scripts/init_variant_batch.py --article-dir {article_dir} --count {variant_count} --source main
3. 生成变体时必须使用 batch skill 默认流程，并保证每个变体写入：
   `{variants_dir}/<angle-slug>/output/others.md`
   `{variants_dir}/<angle-slug>/output/metadata.json`
4. 变体完成后运行 batch skill 要求的单篇校验和相似度检查。
5. 完成后直接结束，不要等待用户继续输入。

要求：
- 不要修改 `{article_dir}/main.md` 和 `{article_dir}/metadata.json`。
- 不要覆盖当前目录外的任何文件。
- 如果某个变体失败，必须在 progress.json 和日志中写清楚失败原因。
- 输出目录必须是 `{variants_dir}/`。
""".strip()
