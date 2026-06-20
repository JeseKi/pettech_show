---
name: wechat-main-variant-rewriter
description: Rewrite one audience-specific article from a local filesystem main article or an exported stored main revision.
---

# WeChat Main Variant Rewriter

Rewrite one audience-specific version from an existing main article.

Prefer the local filesystem contract when the request comes from this repo's TUI workflow. The legacy stored-revision export remains available only for web-app handoffs that provide `main_revision_id` and `handoff_id`.

## Filesystem Workflow

1. Start from a prepared audience directory:
   - `main/<date>/<output_id>/variants/<audience-slug>/task.md`
   - `main/<date>/<output_id>/variants/<audience-slug>/manifest.json`
   - `main/<date>/<output_id>/variants/<audience-slug>/source_article.md`
   - `main/<date>/<output_id>/variants/<audience-slug>/metadata.template.json`
2. Read these references before writing:
   - `../wechat-daily-writer/references/style_reference.md`
3. Write output files under the audience directory's `output/` folder:
   - `others.md`
   - `metadata.json`
4. Use `metadata.template.json` as the starting point for `metadata.json`.
5. Validate and self-fix before handoff:

   ```bash
   python3 .agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py --run-dir main/<date>/<output_id>/variants/<audience-slug>
   ```

   If validation fails, fix `output/others.md` / `output/metadata.json` and rerun validation until it returns `OK`.

## Filesystem Output Contract

`metadata.json` must follow this structure:

```json
{
  "input_mode": "filesystem",
  "output_id": "260505_1",
  "audience_label": "LLM Agent 开发者",
  "article": {
    "role": "variant",
    "file": "others.md",
    "title": "标题",
    "summary": "摘要",
    "tags": ["产品介绍"],
    "search_intents": [
      {
        "role": "primary",
        "意图类型": "教程型",
        "关键词": "AI短剧角色一致性怎么做",
        "搜索意图": "用户正在找可执行的方法来解决角色和场景漂移。",
        "适合文章角度": "用教程或清单结构承接角色资产库、分镜和版本管理。",
        "标题使用建议": "建议完整保留",
        "优先级": "高",
        "来源依据": "由主稿或 material 的搜索入口分配到当前变体。"
      }
    ],
    "based_on_output_id": "260505_1",
    "source_main_file": "main/260505/260505_1/artwork/output/main.md"
  }
}
```

## Legacy Stored-Revision Workflow

1. Run `scripts/export_main_article.py --revision-id <id> --audience <label> --handoff-id <uuid>`.
2. Read:
   - `task.md`
   - `manifest.json`
   - `source_article.md`
   - files under `sources/`
3. Read these references before writing:
   - `../wechat-daily-writer/references/style_reference.md`
4. Write:
   - `others.md`
   - `metadata.json`
5. Use `metadata.template.json` as the starting point for `metadata.json`.
6. Validate and self-fix before handoff:
   - `python3 .agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py --run-dir <run-dir>`
   - If validation fails, fix `others.md` / `metadata.json` and rerun validation until it returns `OK`.

## Legacy Quick Start

```bash
python3 .agents/skills/wechat-main-variant-rewriter/scripts/export_main_article.py --revision-id 35 --audience LLM-Agent-开发者 --handoff-id 2f4e6bc2d9d14974a86065c414ff9d02
```

With an explicit workspace:

```bash
python3 .agents/skills/wechat-main-variant-rewriter/scripts/export_main_article.py --issue-id 12 --revision-id 35 --audience LLM-Agent-开发者 --handoff-id 2f4e6bc2d9d14974a86065c414ff9d02 --run-dir .opencode/runs/issues/12/variants/2f4e6bc2d9d14974a86065c414ff9d02/01 --output-dir .opencode/runs/issues/12/variants/2f4e6bc2d9d14974a86065c414ff9d02/01/output --force
```

## Legacy Output Contract

`metadata.json` must follow this structure:

```json
{
  "issue_id": 12,
  "issue_date": "2026-04-06",
  "handoff_id": "2f4e6bc2d9d14974a86065c414ff9d02",
  "main_revision_id": 35,
  "audience_label": "LLM Agent 开发者",
  "article": {
    "role": "variant",
    "file": "others.md",
    "title": "标题",
    "summary": "摘要",
    "tags": ["产品介绍"],
    "search_intents": [],
    "based_on_revision_id": 35,
    "source_item_ids": [101, 102]
  }
}
```

## Rules

- Filesystem mode input must be a local `main/<date>/<output_id>` article prepared by the batch initializer.
- Legacy mode input must be a stored `main` revision, not a variant revision.
- In legacy mode, the top-level `handoff_id` in `metadata.json` must remain unchanged so the web app can auto-sync this audience output.
- `audience_label` is required. `audience_segment_id` / `audience_segment_name` are optional backward-compatible fields.
- `source_article.md` is the factual anchor. Preserve core facts while changing framing and emphasis.
- `metadata.json.article.search_intents` records the search entries this variant actually covers. Prefer one `role: primary` entry and up to 2 `role: secondary` entries. Do not copy every main-article keyword into every variant.
- When a variant has a clear narrative template, align the search intent with that template: problem-diagnosis should favor pain or troubleshooting entries, method-breakdown should favor tutorial entries, decision-comparison should favor comparison or value-decision entries, and trend-judgment should favor trend entries.
- Before writing, classify the source into `asset_blocks` and `rewrite_zones`.
- `asset_blocks` include fenced code blocks, full prompts, commands, parameters, templates, copyable checklists, tables, image Markdown, links, promotional/contact blocks, prices, and fixed claims. Preserve these with high fidelity; do not summarize, paraphrase, omit, or semantically substitute them to reduce repetition.
- `rewrite_zones` include openings, transitions, explanations, case framing, section titles, usage guidance, conclusions, and conversion placement. Use these zones to make the variant structurally and narratively different.
- Similarity reduction applies to rewrite zones, not mandatory asset blocks. If a prompt/code/template block is the reader-facing deliverable, keep it complete.
- Preserve all marketing / promotional information from the original article. Rewrite it naturally for the target audience, but do not delete it, hard-cut it, or reduce it to fewer marketing blocks than the original.
- Preserve all images from the original article. If the original article contains image Markdown or image placeholders, the variant must also retain them; do not drop any image, and do not output fewer images than the original.
- Marketing information and images are both mandatory retention items. Neither category may be omitted, and neither may be partially dropped.
- The variant must feel materially different for the target audience, but do not explicitly name the audience in the body.
- The public article body must not expose internal work terms such as `source_article`, `source`, `源文`, `源稿`, `原文`, `改写`, `变体`, `叙事模板`, `hook`, `钩子`, or refer to the article as a rewrite of another article.
- `hook` / `钩子` is an internal planning label. Reader-facing headings should use natural labels such as `下一步行动`, `领取方式`, `工具入口`, `落地路径`, or a context-specific benefit title.
- `source_item_ids` must reference only real exported source items.
- `others.md` should read like a complete公众号成稿, not a summary memo.
- Write at the length that makes the audience-specific article complete and useful. Do not pad to satisfy a fixed character target.

## Validation Script

Use this script to verify acceptance criteria in one run directory:

```bash
python3 .agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py --run-dir main/260505/260505_1/variants/llm-agent-开发者
```

Checks include:

- required run files exist (`task.md`, `manifest.json`, `source_article.md`, `metadata.template.json`)
- output files exist (`others.md`, `metadata.json`)
- `others.md` is non-empty; optional `--min-chars` can enforce a minimum only when explicitly requested
- `metadata.json` is valid JSON and includes required contract fields
- `metadata.json.article.role=file` constraints (`variant` + `others.md`)
- filesystem metadata consistency with `manifest.json` (`output_id`, `audience_label`)
- legacy metadata consistency with `manifest.json` (`handoff_id`, `main_revision_id`, `audience_label`)
- legacy `source_item_ids` are integers and reference exported source item IDs
- image reference count does not drop below `source_article.md`
- fenced code block count does not drop below `source_article.md`
- public body does not contain internal source/rewrite terminology
