# -*- coding: utf-8 -*-
"""Background execution for Personal AI Wiki jobs."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, cast

from loguru import logger
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.parser import parse_aiwiki_result
from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.progress import mark_progress_failure, progress_marked_complete
from src.server.opencode import run_opencode_in_tmux

from ..dao import PersonalAiwikiJobDAO
from ..schemas import PersonalAiwikiOperation
from .persistence import manifest_db_payload, read_answer, read_manifest, update_manifest, write_manifest
from .serializers import parse_json_list
from .workspace import personal_aiwiki_root

_WORKSPACE_LOCKS: dict[int, Lock] = {}
_WORKSPACE_LOCKS_GUARD = Lock()


def sync_job_records(db: Session) -> None:
    data_root = personal_aiwiki_root()
    if not data_root.exists():
        return
    dao = PersonalAiwikiJobDAO(db)
    for manifest_path in sorted(data_root.glob("users/user_*/jobs/*_personal_aiwiki/manifest.json")):
        try:
            manifest = read_manifest(manifest_path.parent)
        except Exception as exc:
            logger.warning("跳过无法读取的个人 AI Wiki manifest {}: {}", manifest_path, exc)
            continue
        if manifest.get("status") in {"queued", "running"}:
            manifest["status"] = "failed"
            manifest["message"] = "任务因服务重启中断，请重新提交"
            manifest["finished_at"] = manifest.get("finished_at") or datetime.now(timezone.utc).isoformat()
            write_manifest(manifest_path.parent, manifest)
        dao.upsert_from_payload(manifest_db_payload(manifest))


def run_job(
    job_id: str,
    workdir: Path,
    session_factory: sessionmaker[Session],
) -> None:
    manifest = read_manifest(workdir)
    owner_user_id = int(manifest["owner_user_id"])
    started_at = datetime.now(timezone.utc)
    update_manifest(
        workdir,
        status="running",
        message="正在整理个人知识库",
        started_at=started_at.isoformat(),
        session_factory=session_factory,
    )
    try:
        with workspace_lock(owner_user_id):
            prepare_skill(workdir)
            prepare_opencode_config(workdir)
            run_personal_aiwiki_opencode(workdir)
            if not progress_marked_complete(workdir):
                raise RuntimeError("progress.json 未写入任务完成标记")
            updated = read_manifest(workdir)
            result = parse_aiwiki_result(job_id, Path(updated["workspace_dir"]))
            answer = read_answer(workdir)
            update_manifest(
                workdir,
                status="completed",
                message="个人知识库已更新",
                finished_at=datetime.now(timezone.utc).isoformat(),
                summary=result.summary,
                answer_markdown=answer,
                session_factory=session_factory,
            )
    except Exception as exc:
        logger.exception("Personal AI Wiki job failed: {}", job_id)
        append_log(workdir, f"ERROR: {exc}")
        mark_progress_failure(workdir, str(exc))
        update_manifest(
            workdir,
            status="failed",
            message=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
            session_factory=session_factory,
        )


def run_personal_aiwiki_opencode(workdir: Path) -> None:
    manifest = read_manifest(workdir)
    prompt = build_prompt(
        workdir=workdir,
        workspace_root=Path(str(manifest["workspace_dir"])),
        operation=cast(PersonalAiwikiOperation, manifest["operation"]),
        input_text=manifest.get("input_text"),
        files=parse_json_list(manifest.get("files")),
    )
    run_opencode_in_tmux(
        workdir,
        title="Personal AI Wiki",
        prompt=prompt,
        opencode_dir=workdir.parent.parent,
    )


def build_prompt(
    *,
    workdir: Path,
    workspace_root: Path,
    operation: PersonalAiwikiOperation,
    input_text: Any,
    files: list[dict[str, Any]],
) -> str:
    wiki_path = workspace_root / "wiki"
    file_lines = "\n".join(
        f"- {item.get('filename')}：{item.get('raw_path')}"
        + (
            f"；已复制到个人 workspace：{item.get('workspace_raw_path')}"
            if item.get("workspace_raw_path")
            else ""
        )
        for item in files
    ) or "- 无上传文件"
    operation_goal = """导入资料：读取本次上传/输入的 raw markdown，并把可复用事实、实体、概念、关系、比较、问题沉淀进个人 Wiki。不要复制全文；保留 raw 原文不改。"""
    question_block = str(input_text).strip() if input_text else "无"
    return f"""
你在个人 AI Wiki 任务目录中工作：{workdir.as_posix()}

个人 Wiki workspace：{workspace_root.as_posix()}
WIKI_PATH：{wiki_path.as_posix()}

请严格只读写：
- 当前任务目录：{workdir.as_posix()}
- 当前用户个人 workspace：{workspace_root.as_posix()}
不得访问或修改其他项目目录、其他用户目录或系统目录。

必须使用当前任务目录内的 Skill：$llm-wiki。

进度协议：
- 当前任务目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件，禁止清空或重建已有 events。
- `event` 只能使用 `开始`、`完成` 或 `失败`；`event`、`step`、`summary` 必须使用中文。
- 每开始一个步骤，立刻重写 `progress.json`，追加 `开始` 事件，并把 `status` 设为 `running`。
- 每完成一个步骤，立刻重写 `progress.json`，追加 `完成` 事件。
- 如果任务失败，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 所有工作完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

任务类型：ingest
目标：
{operation_goal}

本次资料：
{file_lines}

用户输入：
{question_block}

输出要求：
- Wiki 内容必须写入 `{wiki_path.as_posix()}` 下；raw 原文保留在 `{(workspace_root / 'raw').as_posix()}`。
- 如果缺少 `SCHEMA.md`、`index.md`、`log.md` 或核心目录，先按 $llm-wiki 初始化。
- 每个新增或更新的词条必须有 YAML frontmatter，至少包含 title、type、created/updated、tags。
- 所有新词条必须能从 `wiki/index.md` 或其它词条通过 wikilink 到达。
- 每次导入后都要更新 `wiki/index.md` 和 `wiki/log.md`。
- 如果有摘要，也可以写入当前任务目录 `answer.md`。
- 完成后直接结束，不要等待用户继续输入。
""".strip()


def workspace_lock(owner_user_id: int) -> Lock:
    with _WORKSPACE_LOCKS_GUARD:
        lock = _WORKSPACE_LOCKS.get(owner_user_id)
        if lock is None:
            lock = Lock()
            _WORKSPACE_LOCKS[owner_user_id] = lock
        return lock


def prepare_skill(workdir: Path) -> None:
    source = Path(__file__).resolve().parent.parent / "skills" / "llm-wiki"
    target_root = workdir / ".agents" / "skills"
    target = target_root / "llm-wiki"
    target_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def build_session_factory(db: Session) -> sessionmaker[Session]:
    bind = db.get_bind()
    if isinstance(bind, Connection):
        bind = bind.engine
    if not isinstance(bind, Engine):
        raise RuntimeError("无法创建个人 AI Wiki 任务会话工厂")
    return sessionmaker(bind=bind, autocommit=False, autoflush=False)
