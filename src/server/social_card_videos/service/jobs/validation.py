# -*- coding: utf-8 -*-
"""Social card video job validation and progress diagnostics."""

from __future__ import annotations

from pathlib import Path

from src.server.aiwiki.service.progress import read_progress


def progress_events_snapshot(workdir: Path) -> list[object]:
    events = read_progress(workdir).get("events")
    return list(events) if isinstance(events, list) else []


def ensure_progress_events_preserved(
    workdir: Path, baseline_events: list[object], stage: str
) -> None:
    events = read_progress(workdir).get("events")
    if not isinstance(events, list):
        raise RuntimeError(f"{stage} 阶段重置了 progress.json：events 缺失或不是数组")
    if len(events) < len(baseline_events) or events[: len(baseline_events)] != baseline_events:
        raise RuntimeError(f"{stage} 阶段重置了 progress.json：必须保留已有 events 并追加新事件")


def incomplete_progress_message(workdir: Path) -> str:
    progress = read_progress(workdir)
    status_text = str(progress.get("status") or "未知")
    current_step = str(progress.get("current_step") or "未知步骤")
    last_event = _describe_last_progress_event(progress)
    issues = _inspect_video_outputs(workdir)
    issue_text = "；".join(issues) if issues else "视频存在，但完成态协议未封口"
    return (
        "轮播视频生成未完成：OpenCode 已退出，但 progress.json 未写入 completed。"
        f" 当前状态：{status_text}，当前步骤：{current_step}，最后事件：{last_event}。"
        f" 发现问题：{issue_text}"
    )


def _describe_last_progress_event(progress: dict[str, object]) -> str:
    events = progress.get("events")
    if not isinstance(events, list):
        return "events 缺失或不是数组"
    if not events:
        return "无"
    last = events[-1]
    if not isinstance(last, dict):
        return "最后一条事件不是对象"
    event = str(last.get("event") or "未知事件")
    step = str(last.get("step") or "未知步骤")
    summary = str(last.get("summary") or "")
    if summary:
        return f"{event}/{step}：{summary}"
    return f"{event}/{step}"


def _inspect_video_outputs(workdir: Path) -> list[str]:
    issues: list[str] = []
    source = workdir / "source"
    if not source.is_dir():
        return ["未生成 source/"]
    deck_dirs = [source / "xhs_guizang"]
    variants_root = source / "xhs_guizang_variants"
    if variants_root.is_dir():
        deck_dirs.extend(path for path in sorted(variants_root.glob("variant-*")) if path.is_dir())
    for deck in deck_dirs:
        if not deck.is_dir():
            continue
        rel = deck.relative_to(workdir).as_posix()
        if not (deck / "video" / "slideshow.mp4").is_file():
            issues.append(f"缺少 {rel}/video/slideshow.mp4")
        if not (deck / "video.md").is_file():
            issues.append(f"缺少 {rel}/video.md")
    return issues

