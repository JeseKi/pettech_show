---
name: wechat-raw-materializer
description: Convert newly added WeChat raw Markdown files under `raw/<date>/` into structured material JSON files under `material/<date>/`. Use when the user asks to 转写 raw 到 material, 将新增 md 入库, 结构化素材, 参考 git status 处理 raw, or create material JSON from local WeChat source Markdown.
---

# WeChat Raw Materializer

Turn local `raw/<date>/*.md` source articles into `material/<date>/*.json` planning assets.

The material file is not a transcript. It is a semantic extraction layer for later article writing and topic wiki maintenance.

## Workflow

1. Run `git status --short` to identify newly added or changed `raw/<date>/` files.
2. Run the planner:
   ```bash
   python3 .agents/skills/wechat-raw-materializer/scripts/materialize_raw.py plan
   ```
   Use `--date YYMMDD` when the user names a date or `git status` only shows a directory.
3. Read existing examples under nearby `material/<date>/` directories to match schema, naming, tone, and depth.
4. Read each raw Markdown source. For long prompt collections, inspect headings and repeated structures; for product/tutorial articles, inspect the pain setup, claimed benefits, concrete steps, images, and conversion hooks.
5. Create one JSON file per raw Markdown file under `material/<date>/`. New or updated material files must include `搜索入口`.
6. Validate:
   ```bash
   python3 .agents/skills/wechat-raw-materializer/scripts/materialize_raw.py validate --date YYMMDD
   python3 .agents/skills/wechat-raw-materializer/scripts/materialize_raw.py validate --date YYMMDD --strict-search-intents --strict-question-topics
   jq empty material/YYMMDD/*.json
   ```
7. Finish by reporting created files and validation status.

## Material Schema

Use this top-level structure:

```json
{
  "元数据": {
    "标题": "原文标题",
    "字数": "原文字符数或既有口径下的长度",
    "分类": ["科技", "AI工具", "教程"],
    "标签": ["ChatGPT", "AI绘图"],
    "raw文件路径": "raw/YYMMDD/原文件.md"
  },
  "文章定位": "这篇素材面向谁，解决什么写作需求",
  "痛点": [],
  "蹭到的热点": [],
  "解决方案": [],
  "选题": [
    "Claude Code 太贵时，普通开发者该怎么降低使用成本？",
    "AI 编程工具配额不够时，团队该如何设计可持续的替代工作流？"
  ],
  "搜索入口": [
    {
      "意图类型": "痛点型",
      "关键词": "Claude Code 太贵",
      "搜索意图": "用户已经感受到价格或额度压力，想判断问题本质或替代方案。",
      "适合文章角度": "从价格焦虑切入，解释 AI 编程工具进入新产品阶段。",
      "标题使用建议": "建议完整保留",
      "优先级": "高",
      "来源依据": "原文围绕 Claude Code 成本、额度和产品阶段变化展开。"
    },
    {
      "意图类型": "教程型",
      "关键词": "Claude Code 怎么省钱",
      "搜索意图": "用户已经接受要用 Claude Code，但想降低订阅、额度或使用成本。",
      "适合文章角度": "从使用成本切入，延伸到更省额度的工作流或替代配置。",
      "标题使用建议": "建议完整保留",
      "优先级": "高",
      "来源依据": "由原文的价格/额度主题词延伸，文章需要能承接省钱方法或成本优化。"
    }
  ],
  "总结": {
    "核心痛点": "",
    "核心热点": "",
    "核心解决方案": ""
  }
}
```

Keep the same Chinese field names as existing material files. Do not invent a different schema unless the repo already changed.

`选题` must remain a string array, but each item must be a complete question that can become an article angle. Do not use tag-like labels such as `Codex额度`, `代理服务`, or `API资源池`. Prefer question titles that name the audience, pain point, and expected solution direction, and end with `？` whenever possible.

`搜索入口` is the source-of-truth field for later keyword-oriented title generation. It is not a generic tag list. Each entry must be a real phrase a user might type into search, and must use one of these fixed `意图类型` values:

- 痛点型
- 教程型
- 对比型
- 替代品型
- 值不值型
- 问题排查型
- 人群场景型
- 趋势观点型

## Search Intent Expansion Rules

`搜索入口` must include both extracted phrases and extended search phrases. Do not only copy keywords that already appear in the raw article.

Use this sequence:

1. Extract seed terms from the raw title, tags, pain points, hotspots, solutions, tool names, product names, pricing words, error words, audience labels, and comparison objects.
2. Turn each seed term into user-search phrases by adding realistic intent modifiers:
   - pain modifiers: `太贵`, `用不起`, `配额不够`, `不稳定`, `失败`, `报错`, `限制`
   - solution modifiers: `怎么办`, `怎么省钱`, `如何解决`, `使用技巧`, `最佳实践`, `教程`
   - decision modifiers: `值不值`, `值得买吗`, `适合谁`, `够用吗`, `怎么选`
   - comparison modifiers: `替代品`, `平替`, `vs`, `和...哪个好`, `对比`
   - audience modifiers: `个人开发者`, `学生`, `新手`, `团队`, `独立开发者`, `普通人`
   - trend modifiers: `趋势`, `未来`, `收费模式`, `产品阶段`, `成本变化`
3. Keep only phrases the raw material can plausibly support. Extended phrases are allowed, but the later article must be able to answer them without title stuffing.
4. Prefer search-entry phrases that sound like real user queries, such as `Claude Code 免费`, `Claude Code 太贵怎么办`, `Claude Code 低价替代`, `Claude Code 和 Cursor 哪个好`, not abstract labels like `AI编程工具趋势`.
5. For each material file, aim for 8-20 `搜索入口` items when the raw source is rich enough. Cover at least 3 intent types when possible.
6. Use `来源依据` to distinguish direct extraction from extension, for example `原文直接讨论价格` or `由价格主题词延伸，文章需承接省钱方案`.

## Extraction Rules

- Understand first, then write. Do not mechanically summarize paragraphs in order.
- `文章定位` should name the audience and practical use of the source article.
- `痛点` should capture user problems, situations, and losses. Include `对应内容` when the raw article gives concrete examples.
- `蹭到的热点` should capture why the topic is timely or clickable: model release, account risk, new tool, platform change, workflow trend, or audience anxiety.
- `解决方案` should capture what the article recommends: product, service, tutorial, workflow, checklist, prompt set, or decision framework.
- `选题` should be reusable article questions, not short labels or article paragraphs. Each item must be a complete question such as `Codex 额度不够时，普通用户该怎么搭建稳定资源池？`; do not write label-only items such as `Codex额度`, `多轮对话`, `代理服务`, or `API资源池`.
- Each `选题` must be directly expandable into a later article and should imply the solution direction supported by `解决方案`.
- `搜索入口` should capture user search-entry phrases, not abstract concepts. Prefer long-tail phrases such as `Claude Code 太贵怎么办`, `AI短剧怎么控制成本`, or `GPT Image 2 怎么生成分镜`.
- `搜索入口` must expand seed terms into adjacent search entries. For example, seed term `Claude Code 价格` can produce `Claude Code 免费`, `Claude Code 太贵`, `Claude Code 低价`, `Claude Code 怎么省钱`, `Claude Code 订阅值不值`, and `Claude Code 替代品` when the raw source can support those angles.
- For each `搜索入口` item, fill `意图类型`, `关键词`, `搜索意图`, `适合文章角度`, `标题使用建议`, `优先级`, and `来源依据`.
- `标题使用建议` should say whether to preserve the phrase completely, preserve the core words, or only use it as a title direction.
- `优先级` should be `高`, `中`, or `低`, based on how strongly the raw article can support the search intent.
- Do not stuff keywords. If the raw article cannot truly answer a phrase, do not include that phrase even if it looks searchable.
- `总结` should compress the strategic value of the material into pain, hotspot, and solution.
- Preserve promotional or conversion details as solution/context only when they affect the writing angle. Do not turn QR codes, coupons, or customer-service copy into first-class assets unless that is the article’s actual solution.
- Do not verify external factual claims unless the user explicitly asks. This task structures local source material; it does not certify claims.

## Naming

Write to:

```text
material/<date>/<date>_<n>_<title>.json
```

Rules:

- Use the raw directory name as `<date>`.
- Continue the next available sequence number in `material/<date>/`.
- If the raw filename already starts with `<date>_<n>_`, reuse that sequence and title when it does not conflict.
- If raw filenames are unnumbered, assign sequence numbers by sorted filename order after existing material files.
- Keep Chinese titles readable. Remove only path-breaking or locally inconsistent characters such as `/` and, when matching existing style, decorative Chinese quote marks around words.
- Set `元数据.raw文件路径` exactly to the local raw path.

## Validation Expectations

Run the bundled validator before finishing. It checks:

- JSON parses.
- Required top-level fields exist.
- `元数据.raw文件路径` points to an existing raw file.
- In normal mode, legacy material files without `搜索入口` still pass.
- With `--strict-search-intents`, every checked material JSON must include a non-empty, well-formed `搜索入口` array.
- `选题` must be a non-empty string array.
- With `--strict-question-topics`, every checked `选题` item must be a question rather than a label.
- Every raw Markdown under the requested date has a material JSON referencing it, unless the user explicitly asked for a subset.

If validation finds missing raw files, create the missing JSON rather than just reporting the gap.
