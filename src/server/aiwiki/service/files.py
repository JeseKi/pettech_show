# -*- coding: utf-8 -*-
"""Uploaded file conversion and preview helpers."""

from __future__ import annotations

import re
import csv
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from statistics import median
from typing import Any
from xml.etree import ElementTree

from fastapi import HTTPException, status

TEXT_PREVIEW_LIMIT = 200_000
XLSX_MAX_ROWS = 200
XLSX_MAX_COLUMNS = 50
CSV_MAX_ROWS = 200
CSV_MAX_COLUMNS = 50
TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}


@dataclass
class PdfTextSpan:
    text: str
    size: float
    flags: int
    font: str


@dataclass
class PdfTextLine:
    spans: list[PdfTextSpan]
    max_size: float
    is_bold: bool
    text: str


def convert_to_markdown(path: Path, content: bytes, extension: str) -> str:
    if extension in TEXT_EXTENSIONS:
        return content.decode("utf-8", errors="replace").strip() + "\n"
    if extension == ".xlsx":
        return xlsx_preview_to_markdown(build_xlsx_preview(path.name, content))
    if extension == ".csv":
        return csv_preview_to_markdown(build_csv_preview(path.name, content))
    if extension == ".pdf":
        return pdf_to_markdown(path.name, content)
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
    if extension == ".csv":
        return build_csv_preview(filename, content)
    if extension == ".pdf":
        markdown = pdf_to_markdown(filename, content)
        return {
            "kind": "pdf",
            "filename": filename,
            "size_bytes": len(content),
            "page_count": pdf_page_count(content, filename),
            "text": markdown[:TEXT_PREVIEW_LIMIT],
            "truncated": len(markdown) > TEXT_PREVIEW_LIMIT,
            "character_count": len(markdown),
        }
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


def build_csv_preview(filename: str, content: bytes) -> dict[str, Any]:
    text = decode_tabular_text(content)
    try:
        sample = text[:8192]
        dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
    except csv.Error:
        dialect = csv.excel

    rows: list[list[str]] = []
    total_rows = 0
    total_columns = 0
    try:
        reader = csv.reader(text.splitlines(), dialect)
        for row in reader:
            total_rows += 1
            normalized = [cell.strip() for cell in row]
            total_columns = max(total_columns, len(normalized))
            if total_rows <= CSV_MAX_ROWS:
                rows.append(normalized[:CSV_MAX_COLUMNS])
    except csv.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV 文件无法读取：{filename}",
        ) from exc

    preview_width = min(max(total_columns, max((len(row) for row in rows), default=0)), CSV_MAX_COLUMNS)
    normalized_rows = [
        [row[index] if index < len(row) else "" for index in range(preview_width)]
        for row in rows
    ]
    sheet = {
        "name": Path(filename).stem or "CSV",
        "row_count": total_rows,
        "column_count": total_columns,
        "truncated": total_rows > CSV_MAX_ROWS or total_columns > CSV_MAX_COLUMNS,
        "rows": normalized_rows,
    }
    return {
        "kind": "spreadsheet",
        "filename": filename,
        "sheets": [sheet],
        "sheet_count": 1,
        "max_rows": CSV_MAX_ROWS,
        "max_columns": CSV_MAX_COLUMNS,
    }


def csv_preview_to_markdown(preview: dict[str, Any]) -> str:
    return xlsx_preview_to_markdown(preview)


def decode_tabular_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def pdf_to_markdown(filename: str, content: bytes) -> str:
    try:
        import fitz  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF 解析依赖 PyMuPDF 未安装。",
        ) from exc

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PDF 文件无法读取：{filename}",
        ) from exc

    try:
        markdown_parts: list[str] = []
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            page_markdown = pdf_page_to_markdown(page)
            if page_markdown:
                markdown_parts.append(page_markdown)
        markdown = cleanup_markdown("\n\n".join(markdown_parts))
        if markdown:
            return markdown + "\n"
        return (
            f"# {Path(filename).stem}\n\n"
            "该 PDF 未抽取到可用文本，可能是扫描件或纯图片文档。\n"
        )
    finally:
        document.close()


def pdf_page_count(content: bytes, filename: str) -> int:
    try:
        import fitz  # type: ignore[import-untyped]

        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PDF 文件无法读取：{filename}",
        ) from exc
    try:
        return int(document.page_count)
    finally:
        document.close()


def pdf_page_to_markdown(page: Any) -> str:
    text_lines = extract_pdf_text_lines(page)
    if not text_lines:
        return ""

    body_size = pdf_body_font_size(text_lines)
    blocks: list[str] = []
    current_paragraph: list[str] = []
    for line in text_lines:
        heading_level = pdf_heading_level(line, body_size)
        if heading_level:
            if current_paragraph:
                blocks.append(" ".join(current_paragraph))
                current_paragraph = []
            heading_text = clean_pdf_inline_text(line.text)
            if heading_text:
                blocks.append(f"{'#' * heading_level} {heading_text}")
            continue

        rendered_line = render_pdf_text_line(line)
        if not rendered_line:
            if current_paragraph:
                blocks.append(" ".join(current_paragraph))
                current_paragraph = []
            continue
        if looks_like_list_item(rendered_line):
            if current_paragraph:
                blocks.append(" ".join(current_paragraph))
                current_paragraph = []
            blocks.append(rendered_line)
            continue
        current_paragraph.append(rendered_line)

    if current_paragraph:
        blocks.append(" ".join(current_paragraph))
    return "\n\n".join(blocks)


def extract_pdf_text_lines(page: Any) -> list[PdfTextLine]:
    text_dict = page.get_text("dict")
    lines: list[PdfTextLine] = []
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for raw_line in block.get("lines", []):
            spans: list[PdfTextSpan] = []
            for raw_span in raw_line.get("spans", []):
                text = str(raw_span.get("text") or "")
                if not text.strip():
                    continue
                spans.append(
                    PdfTextSpan(
                        text=text,
                        size=float(raw_span.get("size") or 0),
                        flags=int(raw_span.get("flags") or 0),
                        font=str(raw_span.get("font") or ""),
                    )
                )
            if not spans:
                continue
            text = clean_pdf_inline_text(" ".join(span.text for span in spans))
            if not text:
                continue
            lines.append(
                PdfTextLine(
                    spans=spans,
                    max_size=max(span.size for span in spans),
                    is_bold=any(pdf_span_is_bold(span) for span in spans),
                    text=text,
                )
            )
    return lines


def pdf_body_font_size(lines: list[PdfTextLine]) -> float:
    sizes = [line.max_size for line in lines if line.max_size > 0]
    if not sizes:
        return 12
    first_pass = float(median(sizes))
    body_candidates = [size for size in sizes if size <= first_pass]
    return float(median(body_candidates or sizes))


def pdf_heading_level(line: PdfTextLine, body_size: float) -> int | None:
    text = line.text.strip()
    if not text or len(text) > 120:
        return None
    if line.max_size >= body_size * 1.55:
        return 1
    if line.max_size >= body_size * 1.28:
        return 2
    if line.is_bold and line.max_size >= body_size * 1.12:
        return 3
    return None


def render_pdf_text_line(line: PdfTextLine) -> str:
    rendered_parts: list[str] = []
    for span in line.spans:
        text = clean_pdf_inline_text(span.text)
        if not text:
            continue
        rendered = apply_pdf_span_markdown(text, span)
        if rendered_parts and not rendered_parts[-1].endswith((" ", "/", "-", "(")):
            rendered_parts.append(" ")
        rendered_parts.append(rendered)
    return cleanup_inline_markdown("".join(rendered_parts))


def apply_pdf_span_markdown(text: str, span: PdfTextSpan) -> str:
    escaped = escape_markdown_inline(text)
    is_bold = pdf_span_is_bold(span)
    is_italic = pdf_span_is_italic(span)
    if is_bold and is_italic:
        return f"***{escaped}***"
    if is_bold:
        return f"**{escaped}**"
    if is_italic:
        return f"*{escaped}*"
    return escaped


def pdf_span_is_bold(span: PdfTextSpan) -> bool:
    return bool(span.flags & 16) or "bold" in span.font.lower()


def pdf_span_is_italic(span: PdfTextSpan) -> bool:
    font = span.font.lower()
    return bool(span.flags & 2) or "italic" in font or "oblique" in font


def looks_like_list_item(value: str) -> bool:
    return bool(re.match(r"^(\*|-|\+|\d+[.)]|[A-Za-z][.)])\s+", value))


def clean_pdf_inline_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def escape_markdown_inline(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", "\\`")


def cleanup_inline_markdown(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def cleanup_markdown(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


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
        ".csv": "text/csv",
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
