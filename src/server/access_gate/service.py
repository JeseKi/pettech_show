# -*- coding: utf-8 -*-
"""
Startup access gate service.

公开接口：
- `initialize_access_token`
- `is_gate_authorized`
- `is_public_request_path`
- `build_gate_page`
- `strip_gate_token_from_url`
"""

from __future__ import annotations

import html
import secrets
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request

ACCESS_GATE_COOKIE_NAME = "pettech_access_gate"
ACCESS_GATE_HEADER_NAME = "X-Access-Gate-Token"
ACCESS_GATE_QUERY_NAME = "_gate_token"
ACCESS_GATE_TOKEN_BYTES = 32

PUBLIC_API_PREFIXES = (
    "/api/interactive-movie/public/",
    "/api/interactive-movie/assets/local/",
)
PUBLIC_API_PATHS = {
    "/api/health",
}
PUBLIC_FRONTEND_PREFIXES = (
    "/interactive-movie/play/",
)
PUBLIC_STATIC_PREFIXES = (
    "/assets/",
)
PUBLIC_STATIC_PATHS = {
    "/favicon.ico",
    "/logo.svg",
    "/vite.svg",
}


def initialize_access_token(project_root: Path) -> str:
    """Generate a fresh startup token and write it to `.token`."""
    token = secrets.token_urlsafe(ACCESS_GATE_TOKEN_BYTES)
    token_path = token_file_path(project_root)
    token_path.write_text(f"{token}\n", encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except OSError:
        pass
    return token


def token_file_path(project_root: Path) -> Path:
    return project_root / ".token"


def read_access_token(project_root: Path) -> str:
    token_path = token_file_path(project_root)
    if not token_path.exists():
        return initialize_access_token(project_root)
    return token_path.read_text(encoding="utf-8").strip()


def is_public_request_path(path: str) -> bool:
    if path in PUBLIC_API_PATHS or path in PUBLIC_STATIC_PATHS:
        return True
    return any(
        path.startswith(prefix)
        for prefix in (
            *PUBLIC_API_PREFIXES,
            *PUBLIC_FRONTEND_PREFIXES,
            *PUBLIC_STATIC_PREFIXES,
        )
    )


def request_gate_token(request: Request) -> str:
    token = request.query_params.get(ACCESS_GATE_QUERY_NAME)
    if token:
        return token
    token = request.headers.get(ACCESS_GATE_HEADER_NAME)
    if token:
        return token
    return request.cookies.get(ACCESS_GATE_COOKIE_NAME, "")


def query_gate_token(request: Request) -> str:
    return request.query_params.get(ACCESS_GATE_QUERY_NAME, "")


def is_valid_token(project_root: Path, token: str) -> bool:
    expected = read_access_token(project_root)
    return bool(token) and secrets.compare_digest(token, expected)


def is_gate_authorized(request: Request, project_root: Path) -> bool:
    return is_valid_token(project_root, request_gate_token(request))


def strip_gate_token_from_url(request: Request) -> str:
    kept_params: list[tuple[str, str]] = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key != ACCESS_GATE_QUERY_NAME
    ]
    query = urlencode(kept_params, doseq=True)
    return f"{request.url.path}?{query}" if query else request.url.path


def build_gate_page(*, path: str, invalid_token: bool = False) -> str:
    escaped_path = html.escape(path, quote=True)
    error_html = (
        '<p class="error">Token 不正确，请检查服务器启动后生成的 .token 文件。</p>'
        if invalid_token
        else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>访问验证</title>
    <style>
      :root {{
        color-scheme: light;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #f5f7fb;
        color: #172033;
      }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
      }}
      main {{
        width: min(92vw, 380px);
        padding: 28px;
        border: 1px solid #d9e0ec;
        border-radius: 8px;
        background: #ffffff;
        box-shadow: 0 18px 45px rgba(23, 32, 51, 0.12);
      }}
      h1 {{
        margin: 0 0 10px;
        font-size: 22px;
        font-weight: 700;
      }}
      p {{
        margin: 0 0 18px;
        color: #5f6b7a;
        line-height: 1.6;
      }}
      label {{
        display: block;
        margin-bottom: 8px;
        font-size: 14px;
        font-weight: 600;
      }}
      input {{
        box-sizing: border-box;
        width: 100%;
        height: 42px;
        border: 1px solid #c7d0df;
        border-radius: 6px;
        padding: 0 12px;
        font: inherit;
      }}
      button {{
        width: 100%;
        height: 42px;
        margin-top: 14px;
        border: 0;
        border-radius: 6px;
        background: #1f6feb;
        color: #ffffff;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }}
      .error {{
        margin-top: 12px;
        margin-bottom: 0;
        color: #b42318;
        font-size: 14px;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>需要访问 Token</h1>
      <p>请输入服务器启动后写入 .token 文件的 token。</p>
      <form action="{escaped_path}" method="get">
        <label for="gate-token">Token</label>
        <input id="gate-token" name="{ACCESS_GATE_QUERY_NAME}" type="password" autocomplete="off" autofocus required />
        <button type="submit">进入</button>
      </form>
      {error_html}
    </main>
  </body>
</html>"""
