# -*- coding: utf-8 -*-
"""Social card job validation and progress diagnostics."""

from __future__ import annotations

from pathlib import Path

from src.server.aiwiki.service.progress import read_progress

from ...schemas import SocialCardResultOut
from ..constants import MAX_SOCIAL_CARD_COUNT, MAX_SOCIAL_POST_COUNT


def coerce_card_count(value: object) -> int:
    try:
        count = int(str(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_SOCIAL_CARD_COUNT))


def coerce_post_count(value: object) -> int:
    try:
        count = int(str(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_SOCIAL_POST_COUNT))


def assert_result_counts(
    *,
    result: SocialCardResultOut,
    post_count: int,
    cards_per_post: int,
) -> None:
    if len(result.posts) != post_count:
        raise RuntimeError(
            f"图文篇数不符：期望 {post_count} 篇，实际 {len(result.posts)} 篇"
        )
    for index, post in enumerate(result.posts, start=1):
        if len(post.images) != cards_per_post:
            raise RuntimeError(
                f"第 {index} 篇图文卡数量不符：期望 {cards_per_post} 张，实际 {len(post.images)} 张"
            )


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


def incomplete_progress_message(
    workdir: Path, *, post_count: int, cards_per_post: int
) -> str:
    progress = read_progress(workdir)
    status_text = str(progress.get("status") or "未知")
    current_step = str(progress.get("current_step") or "未知步骤")
    last_event = _describe_last_progress_event(progress)
    issues = _inspect_social_card_outputs(
        workdir,
        post_count=post_count,
        cards_per_post=cards_per_post,
    )
    issue_text = "；".join(issues) if issues else "产物目录存在，但完成态协议未封口"
    return (
        "小红书图文卡生成未完成：OpenCode 已退出，但 progress.json 未写入 completed。"
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


def _inspect_social_card_outputs(
    workdir: Path, *, post_count: int, cards_per_post: int
) -> list[str]:
    issues: list[str] = []
    first_dir = workdir / "xhs_guizang"
    if not first_dir.is_dir():
        issues.append("未生成 xhs_guizang/")
    else:
        _append_post_output_issues(
            first_dir,
            label="xhs_guizang",
            cards_per_post=cards_per_post,
            issues=issues,
        )
    for post_index in range(2, post_count + 1):
        variant_name = f"variant-{post_index - 1:02d}"
        variant_dir = workdir / "xhs_guizang_variants" / variant_name
        label = f"xhs_guizang_variants/{variant_name}"
        if not variant_dir.is_dir():
            issues.append(f"未生成 {label}/")
            continue
        _append_post_output_issues(
            variant_dir,
            label=label,
            cards_per_post=cards_per_post,
            issues=issues,
        )
    return issues


def _append_post_output_issues(
    post_dir: Path, *, label: str, cards_per_post: int, issues: list[str]
) -> None:
    for filename in ("index.html", "manifest.json", "main.md"):
        if not (post_dir / filename).is_file():
            issues.append(f"缺少 {label}/{filename}")
    output_dir = post_dir / "output"
    if not output_dir.is_dir():
        issues.append(f"缺少 {label}/output/")
        return
    png_count = len([path for path in output_dir.glob("*.png") if path.is_file()])
    if png_count != cards_per_post:
        issues.append(
            f"{label}/output/ PNG 数量不符：期望 {cards_per_post} 张，实际 {png_count} 张"
        )
