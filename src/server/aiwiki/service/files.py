# -*- coding: utf-8 -*-
"""Uploaded file conversion helpers."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fastapi import HTTPException, status


def convert_to_markdown(path: Path, content: bytes, extension: str) -> str:
    if extension == ".docx":
        return extract_docx_text(path).strip() + "\n"
    return content.decode("utf-8", errors="replace").strip() + "\n"


def extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DOCX 文件无法读取：{path.name}",
        ) from exc

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [
            node.text or ""
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[\x00-\x1f/\\:]+", "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:160] or "upload.txt"
