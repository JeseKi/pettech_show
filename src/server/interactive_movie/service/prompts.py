# -*- coding: utf-8 -*-
"""Prompt helpers for interactive movie video generation."""

from __future__ import annotations

from typing import Any


def prompt_template() -> dict[str, Any]:
    """Return a structured prompt helper for future video generation."""
    return {
        "sections": [
            "主体：谁或什么是画面核心，保持描述具体。",
            "动作：主体正在做什么，单镜头只保留一组主要动作。",
            "场景：空间、时代、天气、道具、情绪氛围。",
            "镜头：景别、机位、运镜或镜头切换方式。",
            "时序：按秒描述关键动作变化，例如 [0-2s] / [2-5s]。",
            "风格：写实、动画、电影质感、色彩、光线、材质。",
            "约束：不要出现的内容、主体一致性、字幕/水印限制。",
        ],
        "example": (
            "主体：年轻女性林夏站在老式公寓走廊。\n"
            "动作：[0-2s] 她低头看见门口湿掉的信封；[2-5s] 她缓慢蹲下捡起信，神情迟疑。\n"
            "场景：雨夜，狭窄老公寓走廊，暖黄色灯光闪烁，地面潮湿。\n"
            "镜头：电影级中景缓慢推近，浅景深，轻微手持感。\n"
            "风格：悬疑短片，写实，低饱和，高对比，环境声紧张。\n"
            "约束：不出现文字水印，不切换主角，不夸张恐怖。"
        ),
    }
