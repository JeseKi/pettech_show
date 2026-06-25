# -*- coding: utf-8 -*-
"""Helpers for package-level monkeypatch compatibility."""

from __future__ import annotations

import sys
from typing import Any


def service_attr(name: str, fallback: Any) -> Any:
    if __package__ is None:
        return fallback
    package = sys.modules.get(__package__)
    return getattr(package, name, fallback)
