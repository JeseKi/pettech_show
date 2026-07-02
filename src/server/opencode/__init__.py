# -*- coding: utf-8 -*-
"""Shared OpenCode runtime helpers."""


def run_opencode_in_tmux(*args, **kwargs):
    from .runner import run_opencode_in_tmux as _run_opencode_in_tmux

    return _run_opencode_in_tmux(*args, **kwargs)


__all__ = ["run_opencode_in_tmux"]
