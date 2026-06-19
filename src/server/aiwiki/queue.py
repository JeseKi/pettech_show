# -*- coding: utf-8 -*-
"""Small in-process queue for AI Wiki jobs."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class AiwikiJobQueue:
    def __init__(self, max_workers: int):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="aiwiki-job",
        )
        self._lock = Lock()
        self._pending: list[str] = []
        self._active: set[str] = set()

    def enqueue(self, job_id: str, runner: Callable[[], None]) -> None:
        with self._lock:
            self._pending.append(job_id)
        self._executor.submit(self._run, job_id, runner)

    def queue_position(self, job_id: str) -> int | None:
        with self._lock:
            if job_id in self._active:
                return 0
            try:
                return self._pending.index(job_id) + 1
            except ValueError:
                return None

    def shutdown(self, *, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _run(self, job_id: str, runner: Callable[[], None]) -> None:
        with self._lock:
            if job_id in self._pending:
                self._pending.remove(job_id)
            self._active.add(job_id)
        try:
            runner()
        finally:
            with self._lock:
                self._active.discard(job_id)
