# -*- coding: utf-8 -*-
"""Uploaded file conversion and preview helpers."""

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from fastapi import HTTPException, status

TEXT_PREVIEW_LIMIT = 200_000
XLSX_MAX_ROWS = 200
XLSX_MAX_COLUMNS = 50
TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}


def convert_to_markdown(path: Path, content: bytes, extension: str) -> str:
    if extension in TEXT_EXTENSIONS:
        return content.decode("utf-8", errors="replace").strip() + "\n"
    if extension == ".xlsx":
        return xlsx_preview_to_markdown(build_xlsx_preview(path.name, content))
    if extension == ".pdf":
        return (
            f"# {path.stem}\n\n"
            "该文件是 PDF 文档，目前知识库支持原文预览和留存审计。"
            "如果需要进入 AI Wiki 生成，请补充可抽取的 Markdown/TXT 文本版本。\n"
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"不支持的文件类型：{extension or path.name}",
    )


def build_file_preview(filename: str, content: bytes, extension: str) -> dict[str, Any]:
    if extension in TEXT_EXTENSIONS:
        text = content.decode("utf-8", errors="replace")
        return {
            "kind": "text",
            "format": "plain" if extension == ".txt" else "markdown",
            "text": text[:TEXT_PREVIEW_LIMIT],
            "truncated": len(text) > TEXT_PREVIEW_LIMIT,
            "character_count": len(text),
        }
    if extension == ".xlsx":
        return build_xlsx_preview(filename, content)
    if extension == ".pdf":
        return {"kind": "pdf", "filename": filename, "size_bytes": len(content)}
    return {"kind": "unsupported", "filename": filename}


def build_xlsx_preview(filename: str, content: bytes) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            shared_strings = read_shared_strings(archive)
            sheet_refs = read_workbook_sheets(archive)
            sheets = [
                read_sheet_preview(archive, name, path, shared_strings)
                for name, path in sheet_refs[:20]
            ]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"XLSX 文件无法读取：{filename}",
        ) from exc

    return {
        "kind": "spreadsheet",
        "filename": filename,
        "sheets": sheets,
        "sheet_count": len(sheets),
        "max_rows": XLSX_MAX_ROWS,
        "max_columns": XLSX_MAX_COLUMNS,
    }


def xlsx_preview_to_markdown(preview: dict[str, Any]) -> str:
    lines = [f"# {preview.get('filename') or 'XLSX 表格'}", ""]
    for sheet in preview.get("sheets", []):
        if not isinstance(sheet, dict):
            continue
        rows = sheet.get("rows") if isinstance(sheet.get("rows"), list) else []
        lines.append(f"## Sheet: {sheet.get('name') or 'Sheet'}")
        lines.append("")
        lines.append(f"- 行数：{sheet.get('row_count', 0)}")
        lines.append(f"- 列数：{sheet.get('column_count', 0)}")
        if sheet.get("truncated"):
            lines.append("- 预览已截断，仅包含前 200 行、50 列。")
        lines.append("")
        if rows and all(isinstance(row, list) for row in rows):
            width = max(len(row) for row in rows)
            header = [cell_text(rows[0][index] if index < len(rows[0]) else "") for index in range(width)]
            lines.append("| " + " | ".join(header or ["列"]) + " |")
            lines.append("| " + " | ".join(["---"] * max(width, 1)) + " |")
            for row in rows[1:]:
                values = [cell_text(row[index] if index < len(row) else "") for index in range(width)]
                lines.append("| " + " | ".join(values) + " |")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return [node_text(item) for item in root.findall("{*}si")]


def read_workbook_sheets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib.get("Id"): rel.attrib.get("Target", "")
        for rel in rels.findall("{*}Relationship")
    }
    sheets: list[tuple[str, str]] = []
    for sheet in workbook.findall(".//{*}sheet"):
        name = sheet.attrib.get("name") or "Sheet"
        rel_id = sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        target = rel_map.get(rel_id, "")
        if not target:
            continue
        path = target.lstrip("/")
        if not path.startswith("xl/"):
            path = f"xl/{path}"
        sheets.append((name, path))
    return sheets


def read_sheet_preview(
    archive: zipfile.ZipFile,
    name: str,
    path: str,
    shared_strings: list[str],
) -> dict[str, Any]:
    root = ElementTree.fromstring(archive.read(path))
    rows: list[list[str]] = []
    total_rows = 0
    total_columns = 0

    for row_node in root.findall(".//{*}sheetData/{*}row"):
        total_rows += 1
        row_values: dict[int, str] = {}
        for cell in row_node.findall("{*}c"):
            column_index = cell_column_index(cell.attrib.get("r", ""))
            if column_index <= 0:
                column_index = len(row_values) + 1
            total_columns = max(total_columns, column_index)
            if total_rows <= XLSX_MAX_ROWS and column_index <= XLSX_MAX_COLUMNS:
                row_values[column_index] = cell_value(cell, shared_strings)
        if total_rows <= XLSX_MAX_ROWS:
            preview_width = min(
                max(total_columns, max(row_values.keys(), default=0)),
                XLSX_MAX_COLUMNS,
            )
            rows.append([row_values.get(index, "") for index in range(1, preview_width + 1)])

    return {
        "name": name,
        "row_count": total_rows,
        "column_count": total_columns,
        "truncated": total_rows > XLSX_MAX_ROWS or total_columns > XLSX_MAX_COLUMNS,
        "rows": rows,
    }


def cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find("{*}is")
        return node_text(inline) if inline is not None else ""
    value_node = cell.find("{*}v")
    value = value_node.text if value_node is not None and value_node.text else ""
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return ""
    return value


def node_text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    return "".join(text for text in node.itertext())


def cell_column_index(reference: str) -> int:
    letters = "".join(ch for ch in reference if ch.isalpha()).upper()
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return index


def category_for_extension(extension: str) -> str:
    return "graphic_text" if extension in TEXT_EXTENSIONS else "document"


def default_mime_type(extension: str) -> str:
    return {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pdf": "application/pdf",
    }.get(extension, "application/octet-stream")


def cell_text(value: Any) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ").strip()
    return text or " "


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[\x00-\x1f/\\:]+", "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:160] or "upload.txt"
