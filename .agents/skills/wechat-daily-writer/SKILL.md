---
name: wechat-daily-writer
description: Generate one main WeChat-style article from the local topic wiki, then use referenced `material/<date>/` and `raw/<date>/` files for details. Use when asked to create 主稿, 本地主稿阶段, or write the main article from local wiki/materials.
---

# WeChat Daily Writer

Write one `main` article from the local topic wiki and its referenced source materials.

This skill uses only local filesystem inputs and writes only local filesystem outputs.

## Workflow

1. Read `wiki/index.md` and identify relevant topic candidates from `wiki/topics/`, unless the user names a specific topic/wiki page.
2. Read the selected topic page and its linked `hotspots`, `pain_points`, and `solutions` pages. Use these wiki pages to decide the article's main line, target pain point, current hook, solution angle, and reusable argument structure.
3. If the user provides extra materials, paths, pain points, hot topics, solution angles, or hooks, read and consider them alongside the wiki. User-provided materials can supplement the wiki but should not replace the wiki decision layer unless the user explicitly says to ignore the wiki.
4. From the selected wiki pages, collect referenced `material/<date>/...json` and `raw/<date>/...md` paths. Read the material JSON files first, then inspect each material's `元数据.raw文件路径` and/or explicit wiki raw references to read the corresponding raw Markdown when detail is needed.
5. Read these writing guides before drafting:
   - `assets/system_prompt.md`
   - `assets/output_requirements.md`
   - `references/style_reference.md`
6. Draft only after the wiki decision layer and source-material detail layer are both clear.
7. Choose the output date from today's current date in `YYMMDD` format, unless the user explicitly requests a different publishing/output date. Do not derive the output date from the selected material filename.
8. Choose an `output_id` from the article sequence for the output date, not from the material sequence. The first article for an output date must start at `_1`; then increment by one without gaps. For example, on 2026-05-10 the output date is `260510`; if no `main/260510/260510_*` directory exists, create `main/260510/260510_1/`; if `main/260510/260510_1/` exists, the next new article is `main/260510/260510_2/`.
9. Draft `main/<output_date>/<output_id>/main.md`.
10. Before finalizing `main.md`, verify that the Markdown contains no image syntax, image links, image placeholders, cover blocks, QR-code blocks, or inline image embeds.
11. Create `main/<output_date>/<output_id>/metadata.json`.

## Input Contract

The project root should contain:

- `wiki/`: topic wiki containing `index.md`, `topics/`, `hotspots/`, `pain-points/`, `solutions/`, and `articles/`.
- `material/<date>/`: JSON files with structured material metadata.
- `raw/<date>/`: Markdown source articles referenced by `material/<date>/*.json`.
- `main/<output_date>/`: parent output directory for the current publishing/output date. Each generated article must live in its own `main/<output_date>/<output_id>/` subdirectory.

Use the wiki as the primary planning source:

- `wiki/index.md`: discover active hotspots, reusable pain points, usable solutions, and topic status.
- `wiki/topics/*.md`: choose the core article topic, main judgment, structure, reuse mode, and avoid-list.
- `wiki/hotspots/*.md`: decide why the article is timely now.
- `wiki/pain-points/*.md`: decide audience, scenario, concrete loss, and emotional pressure.
- `wiki/solutions/*.md`: decide what solution to present, how to present it, and which source materials support it.
- `wiki/articles/*.md`: understand previously used article mappings and avoid accidental repetition.

Each material JSON may include fields such as:

- `元数据.标题`
- `元数据.分类`
- `元数据.标签`
- `元数据.raw文件路径`
- `文章定位`
- `痛点`
- `蹭到的热点`
- `解决方案`
- `搜索入口`
- `总结`

Use these fields as the detail and evidence layer after the wiki has selected the topic and source set. Read the raw article when the metadata is too compressed, when procedural detail matters, or when the article needs concrete examples, transitions, screenshots context, original scenarios, or promotional details.

Wiki pages may reference source materials in different forms, including full paths such as `material/260512/example.json`, shorthand IDs such as `material/260518/260518_2`, or explicit raw paths such as `raw/260512/example.md`. Resolve shorthand material IDs by matching files under the referenced `material/<date>/` directory.

## Output Contract

The output directory must be `main/<output_date>/<output_id>/` and must contain:

- `main.md`
- `metadata.json`

Derive `output_id` from the current output date plus the next sequential article number under `main/<output_date>/`. The output date is today's current date in `YYMMDD` format unless the user explicitly provides a different publishing/output date:

- On 2026-05-10, first generated article -> `main/260510/260510_1/`
- On 2026-05-10, second generated article -> `main/260510/260510_2/`
- On 2026-05-10, third generated article -> `main/260510/260510_3/`

When multiple materials are used, the material dates and material sequence numbers do not affect the article output directory. All actual source materials are still recorded in `materials_used`.

Never skip directly to a material's own date or sequence number. For example, if today's output date is `260510`, the second generated article is `main/260510/260510_2/` even if its primary material is `material/260505/260505_5_标题.json`.

`metadata.json` must follow this structure:

```json
{
  "input_mode": "filesystem",
  "output_id": "260510_1",
  "topic": "选题",
  "pain_point": "痛点",
  "solution": "解决方案",
  "hook": "钩子",
  "article": {
    "role": "main",
    "file": "main.md",
    "title": "标题",
    "summary": "摘要",
    "tags": ["产品介绍"],
    "search_intents": [
      {
        "role": "primary",
        "意图类型": "痛点型",
        "关键词": "Claude Code 太贵",
        "搜索意图": "用户已经感受到价格或额度压力，想判断问题本质或替代方案。",
        "适合文章角度": "从价格焦虑切入，解释 AI 编程工具进入新产品阶段。",
        "标题使用建议": "建议完整保留",
        "优先级": "高",
        "来源依据": "来自 material 的搜索入口，本文正文可以承接该问题。"
      }
    ],
    "materials_used": [
      {
        "metadata_file": "material/260505/xxx.json",
        "raw_file": "raw/260505/xxx.md",
        "title": "素材标题"
      }
    ]
  }
}
```

If the user provides a source CSV/table row, a seed row, or explicit production fields, use them for the top-level production metadata:

- `topic`: use the provided row's `topic` value when present and non-empty; otherwise generate the stable searchable topic as usual.
- `pain_point`, `solution`, `hook`: copy the provided row's matching values exactly when present; when absent or empty, write an empty string.

## Rules

- The article title lives in `metadata.json`, not in the Markdown body.
- `metadata.json.article.search_intents` should record the search entries this article can genuinely answer. Include one `role: primary` entry and up to 2-4 `role: secondary` entries when available from material or `wiki/search-intents/`.
- Do not add search intents that the article body cannot support. It is better to record fewer entries than to create fake search coverage.
- The Markdown should read like a finished 公众号主稿, not a task log, local file summary, or release digest.
- Main-article generation is text-only. `main.md` must not contain any images, including Markdown image syntax (`![alt](...)`), raw HTML image tags (`<img ...>`), image placeholders, cover-image blocks, QR-code blocks, or copied image URLs meant for rendering.
- Source images may be read for context, but they must not be copied, embedded, preserved, linked, or represented as placeholders in `main.md`. If an image contains useful evidence, rewrite the evidence as prose instead.
- Do not mention local files, directories, metadata, prompts, or the writing process in the article body.
- Before finalizing `main.md`, scan for source-layer or workflow-layer wording such as `素材`, `材料`, `metadata`, `raw`, `本地文件`, `提示词`, `有素材提到`, `材料显示`, `这篇素材`, or `根据素材`. Rewrite these into reader-facing source language such as `行业报道里提到`, `公开案例里提到`, `有从业者算过一笔账`, `一位创作者的复盘里提到`, or `公开数据里能看到`.
- Use the wiki as the main structured source of truth for deciding what to write and which source materials to use.
- Use `material/<date>/*.json` and `raw/<date>/*.md` as supporting detail sources after they are selected through wiki references or explicit user-provided materials.
- If the user provides additional source files or concrete material paths, read them and include them in the candidate source set even if they are not yet referenced in the wiki.
- You may combine the wiki plan and selected materials with user-provided recent pain points, hot topics, solution angles, and hooks when forming the article.
- Do not fabricate unsupported facts, product capabilities, pricing, metrics, announcements, or guarantees.
- If the wiki's reusable judgment conflicts with material/raw details, trust concrete source details for facts and use the wiki for framing. If the conflict changes the article premise, stop and ask the user or choose a narrower premise that both sources support.
- Do not force a fixed word count. Write at the length that makes the article complete, useful, and natural.
- Do not pad the article to satisfy an old length target.
- Keep the article concise. Remove repeated setup, generic explanation, and filler that does not add facts, judgment, or conversion value.
- If raw/source articles contain screenshots, comparison images, proof points, QR codes, operation examples, covers, or other image assets, omit the image assets from `main.md` and translate only the necessary meaning into text.
- Each key judgment should be supported by concrete arguments drawn from wiki framing, selected material, raw article details, product changes, scenarios, user pain points, likely impact, or solution design.
- Those arguments do not need explicit citations or links, but they do need to be written into the body as part of the reasoning.
- Use `references/style_reference.md` and `assets/output_requirements.md` for pacing, density, and finished-article calibration.
