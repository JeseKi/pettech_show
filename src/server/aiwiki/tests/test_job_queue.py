# -*- coding: utf-8 -*-
from __future__ import annotations

from threading import Event

from src.server.aiwiki.queue import AiwikiJobQueue


def test_cancel_pending_job_prevents_runner() -> None:
    queue = AiwikiJobQueue(max_workers=1)
    first_can_finish = Event()
    first_started = Event()
    cancelled_started = Event()

    def wait_runner() -> None:
        first_started.set()
        first_can_finish.wait(timeout=2)

    queue.enqueue("running-job", wait_runner)
    assert first_started.wait(timeout=2)
    queue.enqueue("cancelled-job", cancelled_started.set)
    assert queue.queue_position("cancelled-job") == 1

    queue.cancel("cancelled-job")
    first_can_finish.set()
    queue.shutdown(wait=True)

    assert queue.queue_position("cancelled-job") is None
    assert not cancelled_started.is_set()
