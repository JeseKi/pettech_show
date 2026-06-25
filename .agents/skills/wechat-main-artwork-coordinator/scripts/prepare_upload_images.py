#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image, ImageOps
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: Pillow. Install project dependencies first, for example: uv sync"
    ) from exc


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_MAX_BYTES = 500 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare rendered artwork images for upload by converting them to JPG under a size limit."
    )
    parser.add_argument(
        "images",
        nargs="*",
        help="Image files to prepare. Optional when --article-dir is provided.",
    )
    parser.add_argument(
        "--article-dir",
        help="Article directory such as main/260505/260505_1. Auto-discovers artwork cover and illustration images.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for upload-ready JPG files. Defaults to <article-dir>/artwork/upload_ready or ./upload_ready.",
    )
    parser.add_argument(
        "--max-kb",
        type=int,
        default=500,
        help="Maximum output size in KB. Default: 500.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON manifest instead of human-readable lines.",
    )
    return parser.parse_args()


def iter_article_images(article_dir: Path) -> Iterable[Path]:
    artwork_dir = article_dir / "artwork"
    found_legacy_outputs = False
    for image_dir in [
        artwork_dir / "cover" / "images",
        artwork_dir / "illustrations" / "images",
    ]:
        if not image_dir.is_dir():
            continue
        for path in sorted(image_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                found_legacy_outputs = True
                yield path

    if found_legacy_outputs:
        return

    guizang_output_dir = artwork_dir / "guizang" / "output"
    if not guizang_output_dir.is_dir():
        return
    for path in sorted(guizang_output_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def unique_output_path(output_dir: Path, source: Path, used: set[Path]) -> Path:
    candidate = output_dir / f"{source.stem}.jpg"
    if candidate not in used and not candidate.exists():
        used.add(candidate)
        return candidate

    counter = 2
    while True:
        candidate = output_dir / f"{source.stem}-{counter}.jpg"
        if candidate not in used and not candidate.exists():
            used.add(candidate)
            return candidate
        counter += 1


def convert_to_rgb(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        background = Image.new("RGB", image.size, (255, 255, 255))
        alpha = image.convert("RGBA").getchannel("A")
        background.paste(image.convert("RGB"), mask=alpha)
        return background
    return image.convert("RGB")


def save_jpeg(image: Image.Image, output_path: Path, quality: int) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        output_path,
        "JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )
    return output_path.stat().st_size


def shrink_image(image: Image.Image, factor: float) -> Image.Image:
    width, height = image.size
    new_size = (
        max(1, math.floor(width * factor)),
        max(1, math.floor(height * factor)),
    )
    return image.resize(new_size, Image.Resampling.LANCZOS)


def prepare_image(source: Path, output_path: Path, max_bytes: int) -> dict[str, object]:
    with Image.open(source) as opened:
        image = convert_to_rgb(opened)

    original_size = source.stat().st_size

    size = save_jpeg(image, output_path, quality=95)
    if size <= max_bytes:
        return result(source, output_path, original_size, size, 95, image.size, "converted")

    for quality in range(90, 34, -5):
        size = save_jpeg(image, output_path, quality=quality)
        if size <= max_bytes:
            return result(source, output_path, original_size, size, quality, image.size, "compressed")

    working = image
    quality = 35
    for _ in range(12):
        factor = max(0.25, math.sqrt(max_bytes / max(size, 1)) * 0.92)
        if factor >= 0.98:
            factor = 0.9
        working = shrink_image(working, factor)
        size = save_jpeg(working, output_path, quality=quality)
        if size <= max_bytes:
            return result(
                source,
                output_path,
                original_size,
                size,
                quality,
                working.size,
                "resized",
            )

    raise SystemExit(
        f"Could not reduce image below {max_bytes} bytes: {source} -> {output_path} ({size} bytes)"
    )


def result(
    source: Path,
    output_path: Path,
    original_size: int,
    output_size: int,
    quality: int,
    dimensions: tuple[int, int],
    action: str,
) -> dict[str, object]:
    return {
        "source": source.as_posix(),
        "upload_path": output_path.as_posix(),
        "original_bytes": original_size,
        "upload_bytes": output_size,
        "quality": quality,
        "width": dimensions[0],
        "height": dimensions[1],
        "action": action,
    }


def default_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    if args.article_dir:
        return Path(args.article_dir) / "artwork" / "upload_ready"
    return Path("upload_ready")


def main() -> int:
    args = parse_args()
    max_bytes = args.max_kb * 1024
    if max_bytes <= 0:
        raise SystemExit("--max-kb must be positive")

    sources: list[Path] = []
    if args.article_dir:
        sources.extend(iter_article_images(Path(args.article_dir)))
    sources.extend(Path(value) for value in args.images)

    sources = [path for path in sources if path.is_file()]
    if not sources:
        raise SystemExit("No input images found.")

    output_dir = default_output_dir(args)
    output_dir.mkdir(parents=True, exist_ok=True)
    used: set[Path] = set()
    prepared = [
        prepare_image(source, unique_output_path(output_dir, source, used), max_bytes)
        for source in sources
    ]

    manifest_path = output_dir / "manifest.json"
    manifest = {
        "max_bytes": max_bytes,
        "images": prepared,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps({**manifest, "manifest_path": manifest_path.as_posix()}, ensure_ascii=False, indent=2))
    else:
        for item in prepared:
            print(
                f"{item['upload_path']} ({item['upload_bytes']} bytes, "
                f"{item['action']}, quality={item['quality']})"
            )
        print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
