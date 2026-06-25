---
name: wechat-main-artwork-coordinator
description: Coordinate local WeChat cover and in-article visual card generation for a filesystem main article under `main/<date>/<output_id>/`. Use when asked to add artwork, generate cover, 配图, 生成封面, 插图, or create local visual assets for a generated WeChat long article.
---

# WeChat Main Artwork Coordinator

Coordinate one local artwork pass for a generated main article directory.

Use `guizang-social-card-skill` as the visual production path. Do not use KiVault, cloud uploads, `imagegen`, `grsai-image-generator`, or any AI image generation tool. If a visual needs a specific fictional scene or composite image, solve it with sourced images, screenshots, Guizang layout, typography, diagrams, or information-card design.

## Target Article

Resolve the target article directory before starting:

- If the user gives a directory such as `main/260505/260505_1`, use it.
- If the user gives an output id such as `260505_1`, use `main/260505/260505_1/`.
- If the user gives a concrete `main.md` or `metadata.json` path, use that file's parent directory.
- If no target is provided, use the most recently modified `main/*/*/main.md`.

The target directory must contain:

- `main.md`
- `metadata.json`

## Workflow

1. Run:

   ```bash
   python3 .agents/skills/wechat-main-artwork-coordinator/scripts/init_artwork.py --article-dir main/<date>/<output_id>
   ```

2. Read:
   - `main/<date>/<output_id>/main.md`
   - `main/<date>/<output_id>/metadata.json`
   - `main/<date>/<output_id>/artwork/task.md`
   - `main/<date>/<output_id>/artwork/manifest.json`
3. Create `main/<date>/<output_id>/artwork/visual_brief.json` first.
4. Use `guizang-social-card-skill` to produce:
   - one WeChat `21:9` main cover;
   - one WeChat `1:1` square cover when useful for thumbnails;
   - two in-article visual cards, usually `16:9` or `3:4` depending on the article section.
5. Prefer sourced images and evidence layers over generated art:
   - Use Pexels, Unsplash, Flickr, Wallhaven, or direct web search when a photo layer helps.
   - For factual/product/tutorial/news content, use screenshots or sourced images where available.
   - Record every fetched asset in `artwork/guizang/assets/SOURCES.md`.
   - Do not ask the user the Guizang "A/B/C image source" intake question in this coordinator flow; choose web-sourced images yourself when no user image exists.
   - Do not add visible photo attribution unless the user explicitly asks. Source records still belong in `SOURCES.md`.
6. Save Guizang working files under `main/<date>/<output_id>/artwork/guizang/`:
   - `index.html`
   - `plan.md` or `prompts.md`
   - `manifest.json`
   - `assets/`
   - `output/*.png`
7. Copy or save final rendered files under:
   - Cover images: `artwork/cover/images/`
   - Inline images: `artwork/illustrations/images/`
8. Prepare local delivery images:

   ```bash
   python3 .agents/skills/wechat-main-artwork-coordinator/scripts/prepare_upload_images.py --article-dir main/<date>/<output_id>
   ```

   The prepared JPG files under `artwork/upload_ready/` are local delivery artifacts. Do not upload them to any service.
9. Write final integrated files under `main/<date>/<output_id>/artwork/output/`.

## Local Path Contract

The final output directory is `main/<date>/<output_id>/artwork/output/` and must contain:

- `main.md`
- `metadata.json`
- `assets.json`

Rules:

- `visual_brief.json` must be produced before Guizang rendering.
- AI bitmap generation and cloud uploads are prohibited in this skill.
- The source `main.md` and `metadata.json` in the article directory should remain unchanged unless the user explicitly asks to replace them with the artwork-enhanced output.
- Image references in `assets.json`, `metadata.json`, and `output/main.md` must be absolute filesystem paths produced from actual local files under the current article directory.
- Prefer prepared JPG files under `artwork/upload_ready/` for final references. If they are not available, reference the rendered files under `artwork/cover/images/` and `artwork/illustrations/images/`.
- `metadata.json.article.file` must point to `main.md` in the final output directory.

`assets.json` must use this shape:

```json
{
  "input_mode": "filesystem",
  "output_id": "260505_1",
  "cover_image_path": "/abs/path/to/artwork/upload_ready/cover-21x9.jpg",
  "inline_image_paths": [
    "/abs/path/to/artwork/upload_ready/inline-01.jpg"
  ]
}
```

`metadata.json` must preserve the original article metadata and add/update an artwork object:

```json
{
  "input_mode": "filesystem",
  "output_id": "260505_1",
  "article": {
    "role": "main",
    "file": "main.md",
    "title": "标题",
    "summary": "摘要"
  },
  "artwork": {
    "cover_image_path": "/abs/path/to/artwork/upload_ready/cover-21x9.jpg",
    "inline_image_paths": ["/abs/path/to/artwork/upload_ready/inline-01.jpg"]
  }
}
```
