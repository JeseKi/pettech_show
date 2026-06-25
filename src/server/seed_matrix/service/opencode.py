# -*- coding: utf-8 -*-
"""OpenCode runner and prompt construction for seed matrix jobs."""

from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Any

from src.server.opencode import run_opencode_in_tmux

from ..schemas import SeedMatrixCreate
from .constants import FAILURE_REPORT_PATH, RESULT_CSV_PATH


def run_opencode(workdir: Path, params: dict[str, Any]) -> None:
    _run_opencode_prompt(
        workdir,
        title="Seed matrix generation",
        prompt=build_prompt(workdir, params),
    )


def run_repair_opencode(workdir: Path, params: dict[str, Any], *, error: str) -> None:
    _run_opencode_prompt(
        workdir,
        title="Seed matrix repair",
        prompt=build_repair_prompt(workdir, params, error=error),
    )


def _run_opencode_prompt(workdir: Path, *, title: str, prompt: str) -> None:
    run_opencode_in_tmux(workdir, title=title, prompt=prompt)


def build_prompt(workdir: Path, params: dict[str, Any]) -> str:
    max_seeds = params.get("max_seeds")
    max_seeds_line = f"- max_seeds: {max_seeds}" if max_seeds else "- max_seeds: 不限制"
    hooks = str(params.get("hooks") or "")
    return f"""
你在一个隔离的选题矩阵生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`；`event`、`step` 的值必须使用中文。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件；所有 Skill 和子 Agent 都禁止清空、重置或重建已有 `events`。
- `event` 只能使用 `开始`、`完成` 或 `失败`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `开始` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的中文步骤名。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `完成` 事件，`summary` 简要概括刚完成的内容。
- 如果任务失败，必须先写 `{FAILURE_REPORT_PATH}`，再把 `progress.json` 的 `status` 设为 `failure`、`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 失败事件的 `summary` 必须用一句话写清根因，并包含 `失败报告：{FAILURE_REPORT_PATH}`。
- 所有矩阵生成和校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

失败报告要求：
- 文件路径必须是当前目录下的 `{FAILURE_REPORT_PATH}`。
- 用 Markdown 写一篇完整失败报告，必须包含：失败步骤、失败原因、已检查的输入资产、已执行的命令或校验、关键错误信息、建议处理方式、相关文件路径。
- 不要只写“任务失败”或“未知错误”；如果原因不确定，报告里必须说明已经排除的情况和仍缺少的信息。

目标：
1. 使用 $wechat-seed-matrix-builder，从当前目录的 `material/` 和 `wiki/` 生成选题矩阵 CSV。
2. 输出 CSV 必须写到：`{RESULT_CSV_PATH}`。
3. 生成后运行：
   python3 .agents/skills/wechat-seed-matrix-builder/scripts/validate_seed_matrix.py --source-table {RESULT_CSV_PATH}
4. 校验通过后直接结束，不要等待用户继续输入。

生成参数：
- material_dirs: 当前目录下所有 `material/<date>` 目录
- wiki_dir: wiki
- output_csv: {RESULT_CSV_PATH}
- start_seed: {params.get("start_seed") or "S001"}
- start_day: {params.get("start_day") or "D01"}
- slots_per_day: {params.get("slots_per_day") or 3}
- seeds_per_material: {params.get("seeds_per_material") or 1}
{max_seeds_line}
- hooks: {hooks or "留空"}
- hook_package: {params.get("hook_package") or "留空"}
- primary_hook_ids: {params.get("primary_hook_ids") or "留空"}
- expected_article_count: {params.get("expected_article_count") or 10}

要求：
- 不要覆盖当前目录外的任何文件。
- 不要重新处理 uploads/raw 原文，只使用已存在的 material/wiki 资产。
- 如果 material 有坏文件，按 skill 约束跳过并在日志里说明。
- CSV 必须包含 seed_id、topic、pain_point、solution、hook、mother_topic_prompt 等规划字段。
""".strip()


def build_repair_prompt(workdir: Path, params: dict[str, Any], *, error: str) -> str:
    return f"""
你在一个隔离的选题矩阵生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

后端在 AI 标记完成后执行选题矩阵校验失败，错误如下：
{error}

任务：
1. 修复 `{RESULT_CSV_PATH}`，不要重新处理 uploads/raw 原文。
2. 必须自行运行：
   python3 .agents/skills/wechat-seed-matrix-builder/scripts/validate_seed_matrix.py --source-table {RESULT_CSV_PATH}
3. 如果校验仍失败，继续修复并重跑，直到通过或明确失败原因。

关键生成参数：
- start_seed: {params.get("start_seed") or "S001"}
- max_seeds: {params.get("max_seeds") or "不限制"}
- expected_article_count: {params.get("expected_article_count") or 10}

进度协议：
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件；所有 Skill 和子 Agent 都禁止清空、重置或重建已有 `events`。
- `event`、`step` 的值必须使用中文；`event` 只能使用 `开始`、`完成` 或 `失败`。
- 修复开始时写入 `status: running`，`current_step: 修复选题矩阵`，并追加 `开始` 事件。
- 校验通过后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。
- 如果无法修复，必须先写 `{FAILURE_REPORT_PATH}`，再把 `progress.json` 的 `status` 设为 `failure`、`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 失败事件的 `summary` 必须用一句话写清根因，并包含 `失败报告：{FAILURE_REPORT_PATH}`。

失败报告要求：
- 文件路径必须是当前目录下的 `{FAILURE_REPORT_PATH}`。
- 用 Markdown 写一篇完整失败报告，必须包含：失败步骤、失败原因、已检查的输入资产、已执行的命令或校验、关键错误信息、建议处理方式、相关文件路径。
- 不要只写“任务失败”或“未知错误”；如果原因不确定，报告里必须说明已经排除的情况和仍缺少的信息。
""".strip()


def build_generation_params(
    payload: SeedMatrixCreate, material_count: int
) -> dict[str, Any]:
    params = payload.model_dump()
    expected_seed_count = int(params["expected_seed_count"])
    hooks = format_hooks(params.get("hooks") or [])
    params["start_seed"] = "S001"
    params["start_day"] = "D01"
    params["expected_article_count"] = 10
    params["max_seeds"] = expected_seed_count
    params["seeds_per_material"] = max(1, ceil(expected_seed_count / material_count))
    params["hook_package"] = hooks
    params["primary_hook_ids"] = ""
    return params


def format_hooks(hooks: list[str]) -> str:
    cleaned = [hook.strip() for hook in hooks if hook.strip()]
    return "\n\n".join(f"Hook {index}:\n{hook}" for index, hook in enumerate(cleaned, start=1))
