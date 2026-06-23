# -*- coding: utf-8 -*-
"""OpenCode runner and prompt construction for generic capability jobs."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.progress import progress_marked_complete
from src.server.config import global_config

from ..config import CapabilityConfig


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _skill_source_root(skill_name: str) -> Path:
    configured_root = Path(global_config.project_root) / ".agents" / "skills"
    if (configured_root / skill_name).exists():
        return configured_root

    bundled_root = _repo_root() / ".agents" / "skills"
    if (bundled_root / skill_name).exists():
        return bundled_root

    return configured_root


def prepare_skill(workdir: Path, config: CapabilityConfig) -> None:
    if not config.skill_name:
        return
    source_root = _skill_source_root(config.skill_name)
    source = source_root / config.skill_name
    if not source.exists():
        raise RuntimeError(f"Skill 不存在：{source}")
    target = workdir / ".agents" / "skills" / config.skill_name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def run_opencode(workdir: Path, config: CapabilityConfig, inputs: dict[str, Any]) -> None:
    prepare_skill(workdir, config)
    command = shlex.split(global_config.aiwiki_opencode_command)
    if not command:
        raise RuntimeError("AIWIKI_OPENCODE_COMMAND 不能为空")
    args = [
        *command,
        "run",
        "--dir",
        workdir.as_posix(),
        "--title",
        config.title,
    ]
    if global_config.aiwiki_opencode_model:
        args.extend(["--model", global_config.aiwiki_opencode_model])
    if global_config.aiwiki_opencode_agent:
        args.extend(["--agent", global_config.aiwiki_opencode_agent])
    if global_config.aiwiki_opencode_extra_args:
        args.extend(shlex.split(global_config.aiwiki_opencode_extra_args))
    args.append(build_prompt(workdir, config, inputs))

    log_path = workdir / "logs" / "opencode.log"
    append_log(workdir, "$ " + " ".join(shlex.quote(arg) for arg in args[:-1]) + " <prompt>")
    env = os.environ.copy()
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


def run_validator(workdir: Path, config: CapabilityConfig) -> None:
    if not config.validator_script:
        return
    script = workdir / config.validator_script
    if not script.is_file():
        raise RuntimeError(f"校验脚本不存在：{script}")
    args = [
        sys.executable,
        script.as_posix(),
        "--workdir",
        workdir.as_posix(),
        "--capability-key",
        config.key,
    ]
    append_log(workdir, "$ " + " ".join(shlex.quote(arg) for arg in args))
    process = subprocess.run(
        args,
        cwd=workdir,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(part for part in (process.stdout.strip(), process.stderr.strip()) if part)
    if output:
        append_log(workdir, output)
    if process.returncode != 0:
        raise RuntimeError(f"能力结果校验失败：{output or process.returncode}")


def build_prompt(workdir: Path, config: CapabilityConfig, inputs: dict[str, Any]) -> str:
    if config.skill_name:
        return build_skill_prompt(workdir, config, inputs)
    inputs_json = json.dumps(inputs, ensure_ascii=False, indent=2)
    outputs = "\n".join(f"- {item}" for item in config.outputs)
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(config.steps, start=1))
    return f"""
你在一个隔离的内容能力任务工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

能力名称：{config.title}
能力说明：{config.description}

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`，其中 `event` 使用 `started`、`completed` 或 `failed`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `started` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的事。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `completed` 事件，`summary` 简要概括刚完成的内容。
- 所有内容生成完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"completed","step":"all","summary":"任务完成"}}`。

输入：
```json
{inputs_json}
```

执行步骤：
{steps}

必须输出：
{outputs}

文件输出要求：
1. Markdown 报告必须写到 `output/result.md`。
2. 结构化 JSON 必须写到 `output/result.json`，且顶层必须是 JSON object。
3. `result.json` 至少包含 `title`、`capability_key`、`summary`、`sections`、`next_actions` 字段。
4. 不要在结果中使用 “Demo” 作为能力名称或标题。
5. 完成后直接结束，不要等待用户继续输入。
""".strip()


def build_skill_prompt(workdir: Path, config: CapabilityConfig, inputs: dict[str, Any]) -> str:
    inputs_json = json.dumps(inputs, ensure_ascii=False, indent=2)
    validator = config.validator_script or ""
    validator_command = (
        f"python3 {validator} --workdir . --capability-key {config.key}"
        if validator
        else "无额外校验脚本"
    )
    return f"""
你在一个隔离的内容能力任务工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

能力 key：{config.key}
能力名称：{config.title}
能力说明：{config.description}
必须使用 skill：${config.skill_name}

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`，其中 `event` 使用 `started`、`completed` 或 `failed`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `started` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的事。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `completed` 事件，`summary` 简要概括刚完成的内容。
- 所有内容生成和校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"completed","step":"all","summary":"任务完成"}}`。

输入已经写入 `input/inputs.json`，内容如下：
```json
{inputs_json}
```

目标：
1. 使用 ${config.skill_name} 从 `input/inputs.json` 生成当前能力结果。
2. Markdown 报告必须写到 `output/result.md`。
3. 结构化 JSON 必须写到 `output/result.json`，且必须是严格合法 JSON object。
4. 生成后必须运行：
   {validator_command}
5. 如果校验失败，修正输出文件并重新运行校验，直到通过或明确失败原因。
6. 不要在结果中使用 “Demo” 作为能力名称或标题。
7. 完成后直接结束，不要等待用户继续输入。
""".strip()
