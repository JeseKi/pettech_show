# -*- coding: utf-8 -*-
"""OpenCode runner for AI Wiki jobs."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.server.config import global_config

from .constants import SKILL_NAMES
from .logs import append_log
from .progress import progress_marked_complete


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _skill_source_root() -> Path:
    configured_root = global_config.project_root / ".agents" / "skills"
    if all((configured_root / skill_name).exists() for skill_name in SKILL_NAMES):
        return configured_root

    bundled_root = _repo_root() / ".agents" / "skills"
    if all((bundled_root / skill_name).exists() for skill_name in SKILL_NAMES):
        return bundled_root

    return configured_root


def _opencode_config_source() -> Path | None:
    config_path = global_config.aiwiki_opencode_config_path.strip()
    if not config_path:
        return None

    raw_path = Path(config_path)
    candidates = [raw_path] if raw_path.is_absolute() else [
        global_config.project_root / raw_path,
        _repo_root() / raw_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def prepare_skills(workdir: Path) -> None:
    target_root = workdir / ".agents" / "skills"
    source_root = _skill_source_root()
    target_root.mkdir(parents=True, exist_ok=True)
    for skill_name in SKILL_NAMES:
        source = source_root / skill_name
        if not source.exists():
            raise RuntimeError(f"Skill 不存在：{source}")
        target = target_root / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def prepare_opencode_config(workdir: Path) -> Path | None:
    source = _opencode_config_source()
    if source is None:
        append_log(workdir, "未找到 OpenCode 配置文件，使用 OpenCode 默认配置。")
        return None

    target = workdir / "config.json"
    shutil.copyfile(source, target)
    append_log(workdir, f"已加载 OpenCode 配置文件：{source}")
    return target


def run_opencode(workdir: Path, *, generate_search_assets: bool = True) -> None:
    command = shlex.split(global_config.aiwiki_opencode_command)
    if not command:
        raise RuntimeError("AIWIKI_OPENCODE_COMMAND 不能为空")

    args = [
        *command,
        "run",
        "--dir",
        workdir.as_posix(),
        "--title",
        "AI Wiki materialization",
    ]
    if global_config.aiwiki_opencode_model:
        args.extend(["--model", global_config.aiwiki_opencode_model])
    if global_config.aiwiki_opencode_agent:
        args.extend(["--agent", global_config.aiwiki_opencode_agent])
    if global_config.aiwiki_opencode_extra_args:
        args.extend(shlex.split(global_config.aiwiki_opencode_extra_args))
    args.append(build_prompt(workdir, generate_search_assets=generate_search_assets))

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


def build_prompt(workdir: Path, *, generate_search_assets: bool = True) -> str:
    if generate_search_assets:
        search_asset_goal = """1. 使用 $wechat-raw-materializer 将 raw/<date>/*.md 转成 material/<date>/*.json，并生成 `搜索入口`。
2. 使用 $wechat-topic-wiki 将 material/、raw/ 中的热点、痛点、解决方案、选题、搜索入口沉淀到 wiki/。
3. 生成或更新 wiki/index.md、wiki/log.md，以及 wiki/search-intents/ 下的关键词池词条。
4. 完成后运行：
   python3 .agents/skills/wechat-raw-materializer/scripts/materialize_raw.py validate --strict-search-intents --strict-question-topics
5. 所有内容生成完以后直接结束，不要等待用户继续输入。"""
        search_asset_requirements = """- material JSON 必须包含 热点、痛点、解决方案、关键词/搜索入口、选题、总结。
- 如果 material 包含 搜索入口，必须创建或更新 wiki/search-intents/ 下的关键词池词条。"""
    else:
        search_asset_goal = """1. 使用 $wechat-raw-materializer 将 raw/<date>/*.md 转成 material/<date>/*.json，但本次不要生成 `搜索入口` 字段，也不要扩展搜索关键词。
2. 使用 $wechat-topic-wiki 将 material/、raw/ 中的热点、痛点、解决方案、选题沉淀到 wiki/；本次跳过搜索入口资产。
3. 生成或更新 wiki/index.md 和 wiki/log.md；不要创建或更新 wiki/search-intents/ 关键词池词条。
4. 完成后运行：
   python3 .agents/skills/wechat-raw-materializer/scripts/materialize_raw.py validate --strict-question-topics
5. 所有内容生成完以后直接结束，不要等待用户继续输入。"""
        search_asset_requirements = """- material JSON 必须包含 热点、痛点、解决方案、选题、总结；不要生成 `搜索入口` 字段。
- 不要创建 `wiki/search-intents/`，也不要生成关键词池、搜索入口词条或搜索入口页面。"""

    return f"""
你在一个隔离的 AI Wiki 生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`，其中 `event` 使用 `started`、`completed` 或 `failed`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `started` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的事。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `completed` 事件，`summary` 简要概括刚完成的内容。
- 所有 material、wiki、校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"completed","step":"all","summary":"任务完成"}}`。

目标：
{search_asset_goal}

要求：
{search_asset_requirements}
- wiki 不复制全文，只沉淀可复用资产。
- wiki 相关输出必须落在当前目录的 wiki/ 下，不要写到裸的 topics/、solutions/ 等根目录。
- 输出必须落在当前目录的 material/ 和 wiki/ 下。
""".strip()
