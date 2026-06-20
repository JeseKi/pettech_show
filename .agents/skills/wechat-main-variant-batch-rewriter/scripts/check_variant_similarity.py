#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Soft-check structural and textual similarity across generated variants."
    )
    parser.add_argument(
        "--variants-dir",
        required=True,
        help="Variants directory containing manifest.json and <angle>/output/others.md files.",
    )
    parser.add_argument(
        "--max-source-ratio",
        type=float,
        default=0.78,
        help="Warn when a variant is too similar to the source article. Default: 0.78.",
    )
    parser.add_argument(
        "--max-pair-ratio",
        type=float,
        default=0.72,
        help="Warn when two variants are too similar to each other. Default: 0.72.",
    )
    parser.add_argument(
        "--max-repeated-paragraphs",
        type=int,
        default=8,
        help="Warn when too many non-mandatory paragraphs repeat across variants. Default: 8.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when warnings are found.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def is_mandatory_paragraph(paragraph: str) -> bool:
    if paragraph.startswith("![](") or paragraph.startswith("!["):
        return True
    if paragraph.startswith(">"):
        return True
    patterns = [
        r"后台回复",
        r"优惠券",
        r"客服微信",
        r"https?://",
        r"mp\.weixin\.qq\.com",
        r"需要代充",
        r"订阅优惠使用方法",
        r"更高性价比",
    ]
    return any(re.search(pattern, paragraph, flags=re.IGNORECASE) for pattern in patterns)


def paragraphs(text: str) -> list[str]:
    result: list[str] = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if len(paragraph) < 18 or is_mandatory_paragraph(paragraph):
            continue
        result.append(paragraph)
    return result


def collect_outputs(variants_dir: Path, manifest: dict) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    for item in manifest.get("angles", []):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("slug") or "")
        output_dir = item.get("output_dir")
        if not label or not isinstance(output_dir, str):
            continue
        output_file = Path(output_dir) / "others.md"
        if output_file.exists():
            outputs[label] = output_file
    if outputs:
        return outputs

    for output_file in variants_dir.glob("*/output/others.md"):
        outputs[output_file.parent.parent.name] = output_file
    return dict(sorted(outputs.items()))


def main() -> int:
    args = parse_args()
    variants_dir = Path(args.variants_dir)
    manifest_file = variants_dir / "manifest.json"
    if not manifest_file.exists():
        print(f"ERROR: missing manifest.json: {manifest_file}")
        return 2

    manifest = read_json(manifest_file)
    source_main = Path(str(manifest.get("source_main", "")))
    if not source_main.exists():
        print(f"ERROR: missing source_main: {source_main}")
        return 2

    outputs = collect_outputs(variants_dir, manifest)
    if not outputs:
        print(f"ERROR: no variant outputs found under: {variants_dir}")
        return 2

    source_text = source_main.read_text(encoding="utf-8")
    texts = {label: path.read_text(encoding="utf-8") for label, path in outputs.items()}
    warnings: list[str] = []

    print("Source similarity:")
    for label, text in texts.items():
        score = ratio(source_text, text)
        print(f"- {label}: {score:.3f}")
        if score > args.max_source_ratio:
            warnings.append(
                f"source similarity too high for {label}: {score:.3f} > {args.max_source_ratio:.3f}"
            )

    print("\nPairwise similarity:")
    for left, right in combinations(texts, 2):
        score = ratio(texts[left], texts[right])
        print(f"- {left} <-> {right}: {score:.3f}")
        if score > args.max_pair_ratio:
            warnings.append(
                f"pairwise similarity too high for {left} <-> {right}: {score:.3f} > {args.max_pair_ratio:.3f}"
            )

    paragraph_map: dict[str, list[str]] = {}
    for label, text in texts.items():
        for paragraph in paragraphs(text):
            paragraph_map.setdefault(paragraph, []).append(label)
    repeated = {
        paragraph: labels
        for paragraph, labels in paragraph_map.items()
        if len(labels) >= 2
    }
    print(f"\nRepeated non-mandatory paragraphs: {len(repeated)}")
    if len(repeated) > args.max_repeated_paragraphs:
        warnings.append(
            f"too many repeated non-mandatory paragraphs: {len(repeated)} > {args.max_repeated_paragraphs}"
        )
    for paragraph, labels in sorted(repeated.items(), key=lambda item: (-len(item[1]), -len(item[0])))[:10]:
        preview = re.sub(r"\s+", " ", paragraph)[:100]
        print(f"- [{len(labels)}] {preview}")

    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"- {warning}")
        return 1 if args.strict else 0

    print("\nOK: similarity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
