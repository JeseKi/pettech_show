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
    _run_opencode_prompt(
        workdir,
        config,
        title=config.title,
        prompt=build_prompt(workdir, config, inputs),
    )


def run_repair_opencode(
    workdir: Path, config: CapabilityConfig, inputs: dict[str, Any], *, error: str
) -> None:
    _run_opencode_prompt(
        workdir,
        config,
        title=f"{config.title} JSON repair",
        prompt=build_repair_prompt(workdir, config, inputs, error=error),
    )


def _run_opencode_prompt(
    workdir: Path, config: CapabilityConfig, *, title: str, prompt: str
) -> None:
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


def run_validator(workdir: Path, config: CapabilityConfig, *, json_only: bool = False) -> None:
    if not config.validator_script:
        run_result_json_check(workdir)
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
    if json_only:
        args.append("--json-only")
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


def run_result_json_check(workdir: Path) -> None:
    path = workdir / "output" / "result.json"
    if not path.is_file():
        raise RuntimeError(f"JSON 结果不存在：{path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"result.json 不是合法 JSON：{exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("result.json 必须是 JSON object")
    append_log(workdir, f"OK JSON object: {path.relative_to(workdir).as_posix()}")


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
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`；`event`、`step` 的值必须使用中文。
- `event` 只能使用 `开始`、`完成` 或 `失败`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `开始` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的中文步骤名。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `完成` 事件，`summary` 简要概括刚完成的内容。
- 如果任务失败，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 所有内容生成和 result JSON 校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

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
5. 完成后确保 `output/result.json` 是严格合法 JSON object，然后直接结束，不要等待用户继续输入。
""".strip()


def build_skill_prompt(workdir: Path, config: CapabilityConfig, inputs: dict[str, Any]) -> str:
    inputs_json = json.dumps(inputs, ensure_ascii=False, indent=2)
    validator = config.validator_script or ""
    validator_command = (
        f"python3 {validator} --workdir . --capability-key {config.key} --json-only"
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
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`；`event`、`step` 的值必须使用中文。
- `event` 只能使用 `开始`、`完成` 或 `失败`。
- 每开始一个步骤，立刻重写 `progress.json`，追加一条 `开始` 事件，并把 `status` 设为 `running`、`current_step` 设为当前正在做的中文步骤名。
- 每完成一个步骤，立刻重写 `progress.json`，追加一条 `完成` 事件，`summary` 简要概括刚完成的内容。
- 如果任务失败，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 所有内容生成和 result JSON 校验都完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

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


def build_repair_prompt(
    workdir: Path, config: CapabilityConfig, inputs: dict[str, Any], *, error: str
) -> str:
    inputs_json = json.dumps(inputs, ensure_ascii=False, indent=2)
    validator_command = (
        f"python3 {config.validator_script} --workdir . --capability-key {config.key} --json-only"
        if config.validator_script
        else "python3 -m json.tool output/result.json >/dev/null"
    )
    return f"""
你在一个隔离的内容能力任务工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

能力 key：{config.key}
能力名称：{config.title}
必须使用 skill：${config.skill_name or "无专用 skill"}

后端在 AI 标记完成后执行 result JSON 校验失败，错误如下：
{error}

输入仍以 `input/inputs.json` 为准，内容如下：
```json
{inputs_json}
```

任务：
1. 修复 `output/result.json`，确保它是严格合法 JSON object。
2. 不需要检查或改写 Markdown 报告 `output/result.md`，但不要删除它。
3. 必须自行运行：
   {validator_command}
4. 如果校验仍失败，继续修复并重跑，直到通过或明确失败原因。
5. 不要在结果中使用 “Demo” 作为能力名称或标题。

进度协议：
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `event`、`step` 的值必须使用中文；`event` 只能使用 `开始`、`完成` 或 `失败`。
- 修复开始时写入 `status: running`，`current_step: 修复 result JSON`，并追加 `开始` 事件。
- 校验通过后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。
- 如果无法修复，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件说明原因。
""".strip()
