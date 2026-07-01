#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEFAULT_FONT_CANDIDATES = [
    ".agents/assets/fonts/msyh.ttc",
    ".agents/assets/fonts/msyh.ttf",
    ".agents/assets/fonts/msyhbd.ttc",
    ".agents/assets/fonts/MicrosoftYaHei.ttf",
    ".agents/assets/fonts/NotoSansSC-Regular.otf",
    ".agents/assets/fonts/NotoSansSC-Bold.otf",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def pick_font(config: dict) -> str:
    configured = config.get("font")
    candidates = [configured] if configured else []
    candidates.extend(DEFAULT_FONT_CANDIDATES)
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("No usable CJK font found. Set config.font to a local .ttf/.ttc file.")


def parse_color(value: str | list[int], alpha: int = 255) -> tuple[int, int, int, int]:
    if isinstance(value, list):
        rgb = value[:3]
        return (int(rgb[0]), int(rgb[1]), int(rgb[2]), alpha)
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB color, got {value!r}")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)


def fit_font(text: str, font_path: str, start_size: int, max_width: int, stroke: int, width: int, height: int) -> ImageFont.FreeTypeFont:
    size = start_size
    while size >= 28:
        font = ImageFont.truetype(font_path, size=size)
        draw = ImageDraw.Draw(Image.new("RGBA", (width, height), (0, 0, 0, 0)))
        widest = max(
            draw.textbbox((0, 0), line, font=font, stroke_width=stroke)[2]
            for line in text.split("\n")
            if line
        )
        if widest <= max_width:
            return font
        size -= 4
    return ImageFont.truetype(font_path, size=28)


def draw_multiline_center(
    image: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    y: int,
    fill: tuple[int, int, int, int],
    stroke_fill: tuple[int, int, int, int],
    stroke: int,
) -> None:
    draw = ImageDraw.Draw(image)
    lines = [line for line in text.split("\n") if line]
    bboxes = [draw.textbbox((0, 0), line, font=font, stroke_width=stroke) for line in lines]
    heights = [box[3] - box[1] for box in bboxes]
    line_gap = max(8, int(font.size * 0.16))
    total_h = sum(heights) + line_gap * (len(lines) - 1)
    current_y = y - total_h // 2
    for line, box, h in zip(lines, bboxes, heights):
        w = box[2] - box[0]
        x = (image.width - w) // 2
        draw.text((x, current_y), line, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        current_y += h + line_gap


def make_overlay(
    output_path: Path,
    text: str,
    config: dict,
    font_path: str,
    size_key: str,
    y_key: str,
    stroke_key: str,
    max_width_key: str,
) -> None:
    width = int(config.get("width", 1080))
    height = int(config.get("height", 1440))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    stroke = int(config.get(stroke_key, 8))
    font = fit_font(
        text=text,
        font_path=font_path,
        start_size=int(config.get(size_key, 82)),
        max_width=int(config.get(max_width_key, width - 100)),
        stroke=stroke,
        width=width,
        height=height,
    )
    fill = parse_color(config.get("fill", "#FFDA00"))
    stroke_fill = parse_color(config.get("stroke_fill", "#000000"))
    draw_multiline_center(
        image=image,
        text=text,
        font=font,
        y=int(config.get(y_key, 1180)),
        fill=fill,
        stroke_fill=stroke_fill,
        stroke=stroke,
    )
    image.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render transparent title/subtitle overlays.")
    parser.add_argument("--config", required=True, help="Overlay config JSON.")
    parser.add_argument("--output-dir", required=True, help="Directory for overlay PNG files.")
    args = parser.parse_args()

    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    font_path = pick_font(config)

    title = config.get("title", "").strip()
    if title:
        make_overlay(
            output_dir / "title.png",
            title,
            config,
            font_path,
            "title_font_size",
            "title_y",
            "title_stroke",
            "title_max_width",
        )

    subtitles = config.get("subtitles", [])
    for index, subtitle in enumerate(subtitles, start=1):
        make_overlay(
            output_dir / f"subtitle-{index:02d}.png",
            str(subtitle),
            config,
            font_path,
            "subtitle_font_size",
            "subtitle_y",
            "subtitle_stroke",
            "subtitle_max_width",
        )


if __name__ == "__main__":
    main()
