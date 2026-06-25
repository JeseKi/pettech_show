#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize a local artwork workspace for a filesystem main article."
    )
    parser.add_argument(
        "--article-dir",
        required=True,
        help="Article directory such as main/260505/260505_1. Must contain main.md and metadata.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow resetting an existing artwork workspace.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_workspace(path: Path, force: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not force:
            raise SystemExit(f"Artwork workspace already exists and is not empty: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def article_title(metadata: dict[str, Any]) -> str:
    article = metadata.get("article")
    if isinstance(article, dict):
        title = article.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return ""


def article_summary(metadata: dict[str, Any]) -> str:
    article = metadata.get("article")
    if isinstance(article, dict):
        summary = article.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return ""


def output_id_from(article_dir: Path, metadata: dict[str, Any]) -> str:
    output_id = metadata.get("output_id")
    if isinstance(output_id, str) and output_id.strip():
        return output_id.strip()
    return article_dir.name


def render_task(article_dir: Path, output_id: str, title: str, summary: str) -> str:
    return f"""# 主稿配图协调任务

输入信息：

- input_mode: filesystem
- output_id: {output_id}
- article_dir: {article_dir.as_posix()}
- main_file: {article_dir.as_posix()}/main.md
- metadata_file: {article_dir.as_posix()}/metadata.json
- title: {title or "未填写"}
- summary: {summary or "未填写"}

执行要求：

1. 先产出统一视觉方案，写入 `artwork/visual_brief.json`
2. 使用 `guizang-social-card-skill` 完成封面和正文视觉卡片，不允许使用 imagegen、grsai-image-generator、KiVault 或任何云端上传工具
3. 如无用户提供图片，由 agent 自己从 Pexels / Unsplash / Flickr / Wallhaven / 直接网页搜索选择图源；不需要向用户重复询问三选一
4. 所有外部图源记录到 `artwork/guizang/assets/SOURCES.md`；默认不在图片里加可见署名，除非用户明确要求
5. Guizang 工作文件放在 `artwork/guizang/`，至少保留 `index.html`、`manifest.json`、`plan.md` 或 `prompts.md`、`output/*.png`
6. 封面渲染图复制或保存到 `artwork/cover/images/`
7. 正文配图渲染图复制或保存到 `artwork/illustrations/images/`
8. 必须运行 `.agents/skills/wechat-main-artwork-coordinator/scripts/prepare_upload_images.py --article-dir {article_dir.as_posix()}`，将渲染图转为 `artwork/upload_ready/` 下小于 500KB 的 JPG
9. 不要上传图片到任何云服务；最终引用使用真实存在的本地图片绝对路径
10. `artwork/output/main.md` 和 `artwork/output/assets.json` 中的图片引用必须使用绝对路径，不能使用本地相对路径

最终输出目录：`{article_dir.as_posix()}/artwork/output`

最终必须产出：

- `artwork/output/main.md`
- `artwork/output/metadata.json`
- `artwork/output/assets.json`
"""


def manifest_payload(article_dir: Path, output_id: str) -> dict[str, Any]:
    artwork_dir = article_dir / "artwork"
    return {
        "skill": "wechat-main-artwork-coordinator",
        "input_mode": "filesystem",
        "output_id": output_id,
        "article_dir": article_dir.as_posix(),
        "source_main": (article_dir / "main.md").as_posix(),
        "source_metadata": (article_dir / "metadata.json").as_posix(),
        "artwork_dir": artwork_dir.as_posix(),
        "cover_dir": (artwork_dir / "cover").as_posix(),
        "illustrations_dir": (artwork_dir / "illustrations").as_posix(),
        "guizang_dir": (artwork_dir / "guizang").as_posix(),
        "upload_ready_dir": (artwork_dir / "upload_ready").as_posix(),
        "output_dir": (artwork_dir / "output").as_posix(),
        "visual_production_skill": "guizang-social-card-skill",
        "image_generation_allowed": False,
        "source_image_policy": "agent_web_sourced_by_default",
        "upload_preparation_script": ".agents/skills/wechat-main-artwork-coordinator/scripts/prepare_upload_images.py",
        "upload_max_bytes": 500 * 1024,
        "cloud_upload_allowed": False,
        "final_reference_policy": "absolute_local_paths",
        "final_outputs": [
            "artwork/output/main.md",
            "artwork/output/metadata.json",
            "artwork/output/assets.json",
        ],
    }


def metadata_template(metadata: dict[str, Any], output_id: str) -> str:
    payload = {
        **metadata,
        "input_mode": "filesystem",
        "output_id": output_id,
        "artwork": {
            "cover_image_path": "<absolute-local-path-for-cover>",
            "inline_image_paths": [],
        },
    }
    article = payload.get("article")
    if isinstance(article, dict):
        article["file"] = "main.md"
    return json.dumps(payload, ensure_ascii=False, indent=2)


def assets_template(output_id: str) -> str:
    payload = {
        "input_mode": "filesystem",
        "output_id": output_id,
        "cover_image_path": "<absolute-local-path-for-cover>",
        "inline_image_paths": [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> int:
    args = parse_args()
    article_dir = Path(args.article_dir)
    main_path = article_dir / "main.md"
    metadata_path = article_dir / "metadata.json"
    if not article_dir.is_dir():
        raise SystemExit(f"Article directory not found: {article_dir}")
    if not main_path.exists():
        raise SystemExit(f"Missing article file: {main_path}")
    if not metadata_path.exists():
        raise SystemExit(f"Missing metadata file: {metadata_path}")

    metadata = read_json(metadata_path)
    output_id = output_id_from(article_dir, metadata)
    artwork_dir = article_dir / "artwork"
    ensure_workspace(artwork_dir, args.force)

    for directory in [
        artwork_dir / "cover" / "images",
        artwork_dir / "illustrations" / "images",
        artwork_dir / "guizang" / "assets",
        artwork_dir / "guizang" / "output",
        artwork_dir / "upload_ready",
        artwork_dir / "output",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    write_text(
        artwork_dir / "task.md",
        render_task(article_dir, output_id, article_title(metadata), article_summary(metadata)),
    )
    write_text(
        artwork_dir / "manifest.json",
        json.dumps(manifest_payload(article_dir, output_id), ensure_ascii=False, indent=2),
    )
    write_text(artwork_dir / "output" / "metadata.template.json", metadata_template(metadata, output_id))
    write_text(artwork_dir / "output" / "assets.template.json", assets_template(output_id))

    print(f"Artwork directory: {artwork_dir}")
    print(f"Output directory: {artwork_dir / 'output'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
