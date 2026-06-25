# -*- coding: utf-8 -*-
"""Interactive movie editing services."""

from __future__ import annotations

from .documents import compute_content_hash
from .projects import (
    create_project,
    delete_project,
    get_project,
    get_sync_state,
    list_projects,
    patch_project,
    rename_project,
)
from .prompts import prompt_template
from .releases import (
    close_publication,
    get_public_project,
    list_releases,
    publish_project,
    set_published_release,
)
from .uploads import read_video_upload, upload_video, _s3_client

__all__ = [
    "_s3_client",
    "close_publication",
    "compute_content_hash",
    "create_project",
    "delete_project",
    "get_project",
    "get_public_project",
    "get_sync_state",
    "list_projects",
    "list_releases",
    "patch_project",
    "prompt_template",
    "publish_project",
    "read_video_upload",
    "rename_project",
    "set_published_release",
    "upload_video",
]
