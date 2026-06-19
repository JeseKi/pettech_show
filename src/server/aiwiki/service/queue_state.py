# -*- coding: utf-8 -*-
"""Shared AI Wiki job queue state."""

from __future__ import annotations

from src.server.config import global_config

from ..queue import AiwikiJobQueue

_QUEUE: AiwikiJobQueue | None = None


def get_queue() -> AiwikiJobQueue:
    global _QUEUE
    if _QUEUE is None:
        _QUEUE = AiwikiJobQueue(max_workers=global_config.aiwiki_max_concurrent)
    return _QUEUE


def reset_queue_for_tests() -> None:
    global _QUEUE
    if _QUEUE is not None:
        _QUEUE.shutdown()
    _QUEUE = None
