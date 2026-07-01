# -*- coding: utf-8 -*-
"""Personal AI Wiki context and tool support for chat."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
import json
import re
from typing import Any

import httpx
from fastapi import HTTPException
from loguru import logger

from src.server.auth.models import User
from src.server.config import GlobalConfig
from src.server.personal_aiwiki import service as personal_aiwiki_service

from .http_client import _chat_completions_url, _parse_completion, _post_chat_completion, _upstream_error_detail
from .package_hooks import service_attr
from .streaming import _sse_event

PERSONAL_AIWIKI_TRIGGER = "$知识库"
PERSONAL_AIWIKI_TOOL_NAME = "get_personal_aiwiki_entry"
FRONTEND_CANVAS_TOOL_PREFIX = "frontend_canvas__"
FRONTEND_CANVAS_UNAVAILABLE_MESSAGE = "请在画布中和智能体进行对话, 当前环境无法直接操作画布."
MAX_INDEX_CONTEXT_CHARS = 20_000
MAX_TOOL_CONTENT_CHARS = 60_000
MAX_AUTO_ENTRY_CONTEXT_CHARS = 60_000
MAX_AUTO_ENTRY_COUNT = 4
MAX_TOOL_CALL_STEPS = 5
INDEX_CONTEXT_MARKER = "【个人 AI Wiki 最新索引】"
AUTO_ENTRY_CONTEXT_MARKER = "【个人 AI Wiki 词条全文】"
WIKILINK_PATTERN = re.compile(r"\[\[([^\]\n]+)\]\]")
NO_TOOL_FALLBACK_PHRASES = (
    "没有可调用",
    "没有外部工具",
    "没有工具",
    "不能检索",
    "不能打开",
    "不能读取",
    "不能主动读取",
    "无法打开",
    "无法读取",
    "看不到知识库",
    "看不到具体",
    "看不到里面",
    "只有目录级",
    "目录级信息",
    "不是严格读取",
    "把相关条目内容贴",
    "把知识库条目内容",
    "直接贴给我",
    "如果你的系统支持知识库",
    "没有给我知识库检索",
)


@dataclass(frozen=True)
class PersonalAiwikiChatContext:
    enabled: bool = False
    user_context: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class WikiIndexEntry:
    page: str
    label: str


def build_personal_aiwiki_chat_context(user: User | None, prompt_text: str) -> PersonalAiwikiChatContext:
    if user is None:
        return PersonalAiwikiChatContext()

    user_context = ""
    if PERSONAL_AIWIKI_TRIGGER in prompt_text:
        workspace_root = personal_aiwiki_service.user_workspace_root(int(user.id))
        personal_aiwiki_service.ensure_workspace(workspace_root)
        index_path = workspace_root / "wiki" / "index.md"
        index_markdown = index_path.read_text(encoding="utf-8", errors="replace")
        truncated = len(index_markdown) > MAX_INDEX_CONTEXT_CHARS
        if truncated:
            index_markdown = index_markdown[:MAX_INDEX_CONTEXT_CHARS].rstrip()

        suffix = "\n\n（索引内容过长，已截断到当前演示限制。）" if truncated else ""
        user_context = f"""
{INDEX_CONTEXT_MARKER}
这是一段由用户显式输入 {PERSONAL_AIWIKI_TRIGGER} 后授权注入的个人知识库索引。它不是新的问题，只作为回答上一条用户问题的检索目录。
你已经具备后端工具 `{PERSONAL_AIWIKI_TOOL_NAME}`，可读取当前用户个人 AI Wiki 里的指定词条全文。
规则：
- 如果用户只问“知识库里有哪些内容/有哪些词条”，可以只依据 index 概览回答。
- 如果用户要求基于知识库给出具体正文、事实、结论、推荐、比较、细节、全文、打法/方案，必须先调用 `{PERSONAL_AIWIKI_TOOL_NAME}` 读取相关词条，再回答。
- 不要根据词条标题臆测正文内容；没有读取全文时，只能说“索引显示有这些词条”。
- 不要说无法打开、无法读取、没有工具，也不要要求用户粘贴词条全文。
- 调用工具时，`page` 必须使用 index wikilink 里的路径，优先取 `[[路径|展示名]]` 中 `|` 左侧的路径，例如 `concepts/example`。
- 如果工具返回错误或内容不足，说明具体缺口，不要用通用知识冒充知识库内容。

index.md:
{index_markdown}{suffix}
""".strip()
    return PersonalAiwikiChatContext(
        enabled=True,
        user_context=user_context,
        tools=[personal_aiwiki_tool_definition()],
    )


def personal_aiwiki_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": PERSONAL_AIWIKI_TOOL_NAME,
            "description": (
                "读取当前登录用户个人 AI Wiki 中某个词条页面的完整 Markdown 内容。"
                "当用户要求基于个人知识库回答具体事实、正文、结论、推荐、比较、细节、全文、方案或打法，且当前对话中已有可用词条路径时，必须先调用本工具读取相关词条；"
                "如果用户只需要目录概览或询问有哪些词条，且当前消息已通过 $知识库 注入 index，可以只用 index，不必调用。"
                "参数 page 必须来自 index.md 中的 wikilink 路径，例如 [[concepts/foo|标题]] 应传 concepts/foo；不要传展示标题、不要编造路径。"
                "工具返回 JSON，包含 slug、path、title、type、markdown、truncated；markdown 是回答的主要依据，truncated 为 true 时要提醒用户内容已截断并尽量基于已返回内容回答。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {
                        "type": "string",
                        "description": (
                            "要读取的词条路径。使用 index wikilink 中的路径部分，例如 concepts/product-positioning、"
                            "queries/how-to-build-team；也可以传 wiki/concepts/product-positioning.md 或完整 wikilink，后端会规范化。"
                        ),
                        "minLength": 1,
                    }
                },
                "required": ["page"],
                "additionalProperties": False,
            },
        },
    }


async def complete_with_personal_aiwiki_tools(
    config: GlobalConfig,
    payload: dict[str, Any],
    user: User,
    post_func: Callable[[GlobalConfig, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    post = post_func or service_attr("_post_chat_completion", _post_chat_completion)
    current_payload = without_stream(payload)
    tool_trace: list[dict[str, Any]] = []
    for step in range(1, MAX_TOOL_CALL_STEPS + 1):
        response = await post(config, current_payload)
        tool_calls = extract_tool_calls(response)
        if not tool_calls:
            fallback_payload = build_payload_after_auto_entry_fallback(current_payload, response, user, stream=False)
            if fallback_payload is not None:
                tool_trace.extend(tool_trace_from_auto_entry_payload(fallback_payload))
                return attach_tool_trace(await post(config, fallback_payload), tool_trace)
            return attach_tool_trace(response, tool_trace)
        if has_frontend_tool_call(tool_calls):
            return attach_tool_trace(response, tool_trace)

        tool_trace.extend(tool_trace_from_personal_aiwiki_calls(tool_calls))
        current_payload = build_payload_after_tool_calls(current_payload, response, tool_calls, user, stream=False)

    return attach_tool_trace(tool_loop_limit_response(payload), tool_trace)


async def stream_personal_aiwiki_tool_events(
    config: GlobalConfig,
    payload: dict[str, Any],
    user: User,
    *,
    frontend_canvas_mode: str = "passthrough",
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    post = service_attr("_post_chat_completion", _post_chat_completion)
    current_payload = without_stream(payload)
    handled_frontend_canvas_unavailable = False
    for step in range(1, MAX_TOOL_CALL_STEPS + 1):
        response = await post(config, current_payload)
        tool_calls = extract_tool_calls(response)
        if tool_calls:
            if has_frontend_canvas_tool_call(tool_calls) and frontend_canvas_mode == "unavailable":
                handled_frontend_canvas_unavailable = True
                current_payload = build_payload_after_tool_calls(
                    current_payload,
                    response,
                    tool_calls,
                    user,
                    stream=False,
                    frontend_canvas_mode="unavailable",
                )
                continue
            if has_frontend_tool_call(tool_calls):
                yield "frontend_tool_calls", {"tool_calls": tool_calls}
                yield "done", {}
                return
            current_payload = build_payload_after_tool_calls(current_payload, response, tool_calls, user, stream=False)
            continue

        fallback_payload = build_payload_after_auto_entry_fallback(current_payload, response, user, stream=False)
        if fallback_payload is not None:
            response = await post(config, fallback_payload)
        content = extract_message_content(response)
        if content:
            yield "delta", {"content": content}
        yield "done", {}
        return

    limit_response = (
        frontend_canvas_unavailable_response(payload)
        if handled_frontend_canvas_unavailable
        else tool_loop_limit_response(payload)
    )
    yield "delta", {"content": extract_message_content(limit_response)}
    yield "done", {}


async def stream_personal_aiwiki_sse_events(
    config: GlobalConfig,
    payload: dict[str, Any],
    user: User,
) -> AsyncIterator[str]:
    try:
        async for event, data in stream_personal_aiwiki_tool_events(config, payload, user):
            yield _sse_event(event, data)
    except httpx.TimeoutException:
        yield _sse_event("error", {"message": "Chat API 请求超时"})
    except httpx.HTTPStatusError as exc:
        detail = _upstream_error_detail(exc.response)
        logger.warning(
            "Chat API personal AI Wiki stream upstream error: url={} status={} detail={}",
            _chat_completions_url(config),
            exc.response.status_code,
            detail,
        )
        yield _sse_event("error", {"message": f"Chat API 上游错误：{detail}"})
    except httpx.HTTPError as exc:
        logger.warning("Chat API personal AI Wiki stream request failed: {}", exc)
        yield _sse_event("error", {"message": "Chat API 请求失败"})
    except HTTPException as exc:
        yield _sse_event("error", {"message": str(exc.detail)})
    except ValueError:
        yield _sse_event("error", {"message": "Chat API 返回了无效流式数据"})


def build_payload_after_tool_calls(
    payload: dict[str, Any],
    first_response: dict[str, Any],
    tool_calls: list[dict[str, Any]],
    user: User,
    *,
    stream: bool,
    frontend_canvas_mode: str = "passthrough",
) -> dict[str, Any]:
    messages = [dict(message) for message in payload.get("messages", []) if isinstance(message, dict)]
    messages.append(assistant_tool_message(first_response, tool_calls))
    messages.extend(tool_result_messages(user, tool_calls, frontend_canvas_mode=frontend_canvas_mode))
    final_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"stream", "tool_choice"}
    }
    final_payload["messages"] = messages
    if stream:
        final_payload["stream"] = True
    return final_payload


def without_stream(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"stream", "tool_choice"}
    }


def tool_loop_limit_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": None,
        "model": str(payload.get("model") or ""),
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "个人 AI Wiki 工具调用已暂停。请缩小问题范围或指定一个词条再试。",
                }
            }
        ],
    }


def frontend_canvas_unavailable_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": None,
        "model": str(payload.get("model") or ""),
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": FRONTEND_CANVAS_UNAVAILABLE_MESSAGE,
                }
            }
        ],
    }


def assistant_tool_message(first_response: dict[str, Any], tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    message = first_message(first_response)
    content = message.get("content") if isinstance(message, dict) else ""
    return {
        "role": "assistant",
        "content": content if isinstance(content, str) else "",
        "tool_calls": tool_calls,
    }


def tool_result_messages(
    user: User,
    tool_calls: list[dict[str, Any]],
    *,
    frontend_canvas_mode: str = "passthrough",
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for index, tool_call in enumerate(tool_calls, start=1):
        function = tool_call.get("function") if isinstance(tool_call, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        call_id = tool_call.get("id") if isinstance(tool_call, dict) else None
        if frontend_canvas_mode == "unavailable" and is_frontend_canvas_tool_call(tool_call):
            result = FRONTEND_CANVAS_UNAVAILABLE_MESSAGE
        else:
            result = execute_personal_aiwiki_tool(user, tool_call)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": str(call_id or f"personal_aiwiki_call_{index}"),
                "name": str(name or PERSONAL_AIWIKI_TOOL_NAME),
                "content": result,
            }
        )
    return messages


def build_payload_after_auto_entry_fallback(
    payload: dict[str, Any],
    first_response: dict[str, Any],
    user: User,
    *,
    stream: bool,
) -> dict[str, Any] | None:
    content = extract_message_content(first_response)
    if not should_auto_fetch_entries(content):
        return None

    entries = select_auto_entry_pages(payload)
    if not entries:
        return None

    auto_context = build_auto_entry_context(user, entries)
    if not auto_context:
        return None

    messages = [dict(message) for message in payload.get("messages", []) if isinstance(message, dict)]
    messages.append({"role": "user", "content": auto_context})
    final_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"tools", "tool_choice"}
    }
    final_payload["messages"] = messages
    final_payload["stream"] = stream
    return final_payload


def attach_tool_trace(response: dict[str, Any], trace: list[dict[str, Any]]) -> dict[str, Any]:
    if not trace:
        return response
    next_response = dict(response)
    next_response["tool_trace"] = trace
    return next_response


def tool_trace_from_personal_aiwiki_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        function = tool_call.get("function") if isinstance(tool_call, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        if name != PERSONAL_AIWIKI_TOOL_NAME:
            continue
        arguments = parse_tool_arguments(function.get("arguments") if isinstance(function, dict) else None)
        raw_page = str(arguments.get("page") or arguments.get("slug") or arguments.get("path") or "").strip()
        page = personal_aiwiki_service.normalize_wiki_page(raw_page) if raw_page else ""
        trace.append(
            {
                "kind": "personal_aiwiki_entry",
                "status": "completed",
                "tool": PERSONAL_AIWIKI_TOOL_NAME,
                "page": page or raw_page,
                "source": "tool_call",
            }
        )
    return trace


def tool_trace_from_auto_entry_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return trace
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, str) or AUTO_ENTRY_CONTEXT_MARKER not in content:
            continue
        for match in re.finditer(r"^路径：(.+)$", content, flags=re.MULTILINE):
            page = match.group(1).strip()
            if page:
                trace.append(
                    {
                        "kind": "personal_aiwiki_entry",
                        "status": "completed",
                        "tool": PERSONAL_AIWIKI_TOOL_NAME,
                        "page": page,
                        "source": "auto_fallback",
                    }
                )
    return trace


def should_auto_fetch_entries(content: str) -> bool:
    normalized = content.strip()
    if not normalized:
        return False
    return any(phrase in normalized for phrase in NO_TOOL_FALLBACK_PHRASES)


def select_auto_entry_pages(payload: dict[str, Any]) -> list[WikiIndexEntry]:
    entries = extract_wiki_index_entries(extract_index_context(payload))
    if not entries:
        return []

    prompt = latest_real_user_prompt(payload)
    scored = [(score_index_entry(entry, prompt), index, entry) for index, entry in enumerate(entries)]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _, _, entry in scored[:MAX_AUTO_ENTRY_COUNT]]


def extract_index_context(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and INDEX_CONTEXT_MARKER in content:
            return content
    return ""


def extract_wiki_index_entries(markdown: str) -> list[WikiIndexEntry]:
    entries: list[WikiIndexEntry] = []
    seen: set[str] = set()
    for match in WIKILINK_PATTERN.finditer(markdown):
        raw = match.group(1).strip()
        raw_page, raw_label = raw.split("|", 1) if "|" in raw else (raw, raw)
        page = personal_aiwiki_service.normalize_wiki_page(raw_page)
        if not page or page in seen:
            continue
        seen.add(page)
        label = raw_label.strip() or page.rsplit("/", 1)[-1]
        entries.append(WikiIndexEntry(page=page, label=label))
    return entries


def latest_real_user_prompt(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if INDEX_CONTEXT_MARKER in content or AUTO_ENTRY_CONTEXT_MARKER in content:
            continue
        return content.replace(PERSONAL_AIWIKI_TRIGGER, "").strip()
    return ""


def score_index_entry(entry: WikiIndexEntry, prompt: str) -> int:
    prompt_text = prompt.lower()
    label = entry.label.strip()
    page = entry.page.strip()
    score = 0

    if label and label in prompt:
        score += 20 + min(len(label), 20)
    for chunk in re.split(r"[\s,，。:：、/|()（）《》【】\[\]#-]+", label):
        if len(chunk) >= 2 and chunk in prompt:
            score += 5 + min(len(chunk), 12)

    page_text = page.lower()
    if page_text and page_text in prompt_text:
        score += 15
    for token in re.split(r"[/_\-\s.]+", page_text):
        if len(token) >= 3 and token in prompt_text:
            score += 3

    return score


def build_auto_entry_context(user: User, entries: list[WikiIndexEntry]) -> str:
    parts: list[str] = []
    used_chars = 0
    for entry in entries[:MAX_AUTO_ENTRY_COUNT]:
        try:
            page = personal_aiwiki_service.get_entry_page(user, entry.page)
        except Exception:
            continue

        markdown = page.markdown
        remaining = MAX_AUTO_ENTRY_CONTEXT_CHARS - used_chars
        if remaining <= 0:
            break
        truncated = len(markdown) > remaining
        markdown = markdown[:remaining].rstrip() if truncated else markdown
        used_chars += len(markdown)
        suffix = "\n\n（该词条内容过长，已截断。）" if truncated else ""
        parts.append(f"## {page.title}\n路径：{page.slug}\n\n{markdown}{suffix}")

    if not parts:
        return ""

    return f"""
{AUTO_ENTRY_CONTEXT_MARKER}
后端已经根据上方 index 自动读取了以下词条全文。请直接基于这些正文回答上一条用户问题；不要说没有工具、不能打开链接、无法读取词条或要求用户粘贴资料。若正文仍不足，请明确说明缺口。

{chr(10).join(parts)}
""".strip()


def execute_personal_aiwiki_tool(user: User, tool_call: dict[str, Any]) -> str:
    function = tool_call.get("function") if isinstance(tool_call, dict) else None
    name = function.get("name") if isinstance(function, dict) else None
    if name != PERSONAL_AIWIKI_TOOL_NAME:
        return json.dumps({"error": f"未知工具：{name}"}, ensure_ascii=False)

    arguments = parse_tool_arguments(function.get("arguments") if isinstance(function, dict) else None)
    page = str(arguments.get("page") or arguments.get("slug") or arguments.get("path") or "").strip()
    if not page:
        return json.dumps({"error": "缺少 page 参数"}, ensure_ascii=False)

    try:
        entry = personal_aiwiki_service.get_entry_page(user, page)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    markdown = entry.markdown
    truncated = len(markdown) > MAX_TOOL_CONTENT_CHARS
    if truncated:
        markdown = markdown[:MAX_TOOL_CONTENT_CHARS].rstrip()
    return json.dumps(
        {
            "slug": entry.slug,
            "path": entry.path,
            "title": entry.title,
            "type": entry.type,
            "markdown": markdown,
            "truncated": truncated,
        },
        ensure_ascii=False,
    )


def parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_tool_calls(data: dict[str, Any]) -> list[dict[str, Any]]:
    message = first_message(data)
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    return [item for item in tool_calls if isinstance(item, dict)] if isinstance(tool_calls, list) else []


def has_frontend_tool_call(tool_calls: list[dict[str, Any]]) -> bool:
    for tool_call in tool_calls:
        function = tool_call.get("function") if isinstance(tool_call, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        if isinstance(name, str) and name.startswith("frontend_"):
            return True
    return False


def has_frontend_canvas_tool_call(tool_calls: list[dict[str, Any]]) -> bool:
    return any(is_frontend_canvas_tool_call(tool_call) for tool_call in tool_calls)


def is_frontend_canvas_tool_call(tool_call: dict[str, Any]) -> bool:
    function = tool_call.get("function") if isinstance(tool_call, dict) else None
    name = function.get("name") if isinstance(function, dict) else None
    return isinstance(name, str) and name.startswith(FRONTEND_CANVAS_TOOL_PREFIX)


def extract_message_content(data: dict[str, Any]) -> str:
    message = first_message(data)
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) else _parse_completion(data, requested_model=str(data.get("model") or "")).content


def first_message(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {}
    message = choices[0].get("message")
    return message if isinstance(message, dict) else {}
