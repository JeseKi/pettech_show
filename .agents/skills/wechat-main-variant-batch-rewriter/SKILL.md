---
name: wechat-main-variant-batch-rewriter
description: Generate multiple structurally different WeChat article variants from one local filesystem main article by planning reusable narrative angles and coordinating single-variant rewriter subagents.
---

# WeChat Main Variant Batch Rewriter

Generate multiple visibly different variants from one local `main/<date>/<output_id>` article.
The goal is not audience personalization. The goal is to reuse the same core material while changing the article's narrative structure, opening, argument order, and hook placement.

This skill creates a deterministic `variants/` workspace, plans reusable narrative angles, then processes each angle from that workspace. It orchestrates subagents. Each angle must be assigned to its own subagent, and each subagent must call `wechat-main-variant-rewriter`.

The parent agent must not draft the initial article body. It may initialize workspaces, extract the invariant brief, coordinate runs, review outputs, run similarity checks, and make manual fixes when a subagent result is off-target, malformed, or too similar.

Default subagent runner: use opencode in tmux for the initial variant bodies.
The default opencode model is `deepseek/deepseek-v4-pro`.
One opencode tmux session may write up to 10 variants in the same context. If more variants are requested, split them into chunks of at most 10 and launch the chunks in parallel; there is no hard concurrency cap from this skill.
For example, 9 variants use 1 tmux session; 50 variants use 5 tmux sessions.

## Input

- target article: `main/<date>/<output_id>`, `<output_id>`, a concrete `main.md`, or a concrete `metadata.json`
- optional `angles`: narrative template labels, one per line is preferred
- optional `count`: number of variants to create when angles are not provided; default is 6
- optional source choice:
  - `auto`: prefer `artwork/output/main.md` when it exists, otherwise use `main.md`
  - `artwork`: require `artwork/output/main.md`
  - `main`: use the original `main.md`

Do not ask the user for audience labels unless they explicitly want audience variants. If the user only asks for variants, generate angle-based variants.

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

1. Resolve the target article directory and source article.
2. Normalize the angle list:
   - trim whitespace
   - remove duplicates
   - keep original order
   - if no angles are provided, choose a diverse default set using `--count`
3. Run:

   ```bash
   python3 .agents/skills/wechat-main-variant-batch-rewriter/scripts/init_variant_batch.py --article-dir main/<date>/<output_id> --count 6
   ```

   Or with explicit angles:

   ```bash
   python3 .agents/skills/wechat-main-variant-batch-rewriter/scripts/init_variant_batch.py --article-dir main/<date>/<output_id> --angle 问题诊断型 --angle 分类地图型
   ```

   Use `--source artwork` when the user explicitly wants the illustrated article as the source. Use `--force` only when the user wants to reset an existing `variants/` workspace.
4. Read:
   - `main/<date>/<output_id>/variants/task.md`
   - `main/<date>/<output_id>/variants/manifest.json`
   - `main/<date>/<output_id>/variants/invariant_brief.md`
   - `main/<date>/<output_id>/variants/angle_plan.json`
5. Complete or refine `invariant_brief.md` before spawning subagents. This is parent-agent planning, not article drafting. The brief must identify:
   - `hotspot`: the timely event, trend, release, or trigger
   - `pain`: the reader problem, failure mode, cost, or confusion
   - `solution`: the recommended method, product path, judgment standard, or workflow
   - `next_action`: the conversion or retention element, such as coupon, tutorial, service, product link, customer service, or next action
   - `asset_blocks`: executable or copyable deliverables that must survive with high fidelity, such as prompts, code, parameters, templates, checklists, image Markdown, links, promotional blocks, prices, names, and claims
   - `rewrite_zones`: explanatory prose that may be reframed, reordered, compressed, expanded, or semantically rewritten
6. If the default angle plan does not fit the source article, edit `angle_plan.json` before spawning. Use generic narrative templates, not audience labels. For template guidance, read `references/angle_templates.md`.
7. Process angles serially in the normalized order.
8. For each angle, use the angle directory created under `main/<date>/<output_id>/variants/<angle-slug>/`.
9. Default runner: invoke opencode as the variant-writing subagent through tmux:

   ```bash
   python3 .agents/skills/wechat-main-variant-batch-rewriter/scripts/start_opencode_variant_tmux.py \
     --variants-dir main/<date>/<output_id>/variants \
     --model deepseek/deepseek-v4-pro \
     --max-variants-per-session 10
   ```

   This script renders one prompt per chunk under `variants/opencode/prompts/`, starts one tmux session per chunk, and writes logs under `variants/opencode/logs/`.
   Each opencode session receives the source article, invariant brief, angle plan, and up to 10 assigned angle directories. It must write each assigned angle's `output/others.md` and `output/metadata.json`, then run the single-variant validator for each assigned run directory.
10. If opencode is unavailable, fall back to the original per-angle subagent behavior: for each angle, spawn or invoke a dedicated subagent with that angle directory, and that subagent must call `wechat-main-variant-rewriter`.
11. The parent agent must not write the initial body directly, even if the rewrite looks straightforward.
12. Wait for all opencode tmux sessions to finish. Inspect every `variants/opencode/logs/session-*.log` for failures before accepting outputs.
13. After each subagent returns and the output exists, review the generated result:
   - accept it if it meets the brief
   - manually adjust only when the result does not meet expectations, is incomplete, structurally wrong, drops mandatory content, or is too similar
14. Validate each angle after opencode finishes, even if opencode already ran validation:

   ```bash
   python3 .agents/skills/wechat-main-variant-rewriter/scripts/validate_variant_output.py --run-dir main/<date>/<output_id>/variants/<angle-slug>
   ```

15. After all variants are complete, run the batch similarity soft check:

   ```bash
   python3 .agents/skills/wechat-main-variant-batch-rewriter/scripts/check_variant_similarity.py --variants-dir main/<date>/<output_id>/variants
   ```

   If the check reports high source similarity, high pairwise similarity, repeated paragraphs, or repeated opening structure, revise the offending variants.
16. Report which angles succeeded and where their output directories are.

## Narrative Rules

- Preserve invariant material and asset blocks, not the source article's explanatory skeleton.
- Each variant must use a different narrative template and change opening style, section order, argument sequence, and hook placement.
- Do not reuse the source article's paragraph order unless the selected angle explicitly requires a close guide/list format.
- Avoid repeated exact paragraphs across variants except mandatory links, images, coupon text, and contact blocks.
- The same hotspot, pain, solution, and hook may appear in every variant, but not in the same order every time.
- Marketing/promotional information and image Markdown from the source remain mandatory retention items.
- The body should not say "this is written for..." or expose the angle/template name.
- The body must not expose internal editing terms such as `source_article`, `source`, `源文`, `源稿`, `原文`, `改写`, `变体`, `叙事模板`, `hook`, or `钩子`.
- `hook` / `钩子` is an internal planning label. In reader-facing prose, express it naturally as `下一步行动`, `领取方式`, `工具入口`, `落地路径`, or another context-specific section title.

## Asset Fidelity Rules

Some main articles are not primarily opinion pieces; they are executable asset articles. Examples include prompt collections, code tutorials, parameter recipes, templates, checklists, link directories, and coupon/contact blocks.

For these articles, split the source before rewriting:

- `asset_blocks`: fenced code blocks, full prompts, commands, parameters, copyable templates, tables, links, image Markdown, promotional/contact blocks, prices, and claims. Preserve these with high fidelity. Do not summarize, paraphrase, omit, or "optimize" them unless the user explicitly asks.
- `rewrite_zones`: openings, explanations, transitions, case framing, conclusions, and usage guidance. These are the main surface for narrative variation and semantic rewriting.

Similarity control applies differently by layer:

- Asset blocks may remain highly similar or identical across variants.
- Rewrite zones should change framing, order, examples, section titles, and transitions.
- Similarity checks should ignore or discount fenced code blocks, images, fixed links, coupon/contact blocks, and other mandatory assets.
- If high similarity is caused only by mandatory asset blocks, do not revise those assets just to lower similarity.

For prompt-heavy articles, a valid variant usually keeps every full prompt block and changes the reader-facing wrapper around those prompts: problem setup, selection guidance, risk reminders, usage notes, and next-step framing.

## Angle Templates

Use reusable narrative templates rather than domain-specific templates. Common templates include:

- `问题诊断型`: common mistake -> why it fails -> judgment standards -> correct path -> hook
- `案例复盘型`: concrete failure scene -> cause analysis -> better choice -> hook
- `成本账型`: surface gain -> hidden cost -> risk comparison -> better ROI path -> hook
- `方法论拆解型`: principle -> modules -> why each module works -> reusable method -> hook
- `分类地图型`: category framework -> use cases / risks -> selection path -> hook
- `清单自查型`: self-check questions -> risk/quality score -> action path -> hook
- `反常识型`: reject a familiar belief -> identify the real variable -> new priority order -> hook
- `趋势判断型`: what changed -> why old playbook fails -> new standard -> action suggestion -> hook
- `路径选择型`: decision forks -> cost/benefit/risk comparison -> recommended path -> hook

Read `references/angle_templates.md` when you need selection guidance or detailed structure.
When `--count` exceeds the built-in template count, the initializer creates numbered custom `扩展叙事型NN` angle labels so large batches such as 50 variants can still be chunked into opencode sessions.

## Notes

- The final output root is `main/<date>/<output_id>/variants/`.
- Each angle output is independent and must keep its own output directory.
- The default source article is the TUI artwork result when present: `main/<date>/<output_id>/artwork/output/main.md`.
- The downstream `wechat-main-variant-rewriter` validator still requires `audience_label`; in this batch workflow that field stores the angle label for compatibility.
- Writing the variant body directly in the parent agent is forbidden; that content must originate from the angle subagent first.
- The default angle subagent is an opencode tmux session using `deepseek/deepseek-v4-pro`; one session may write up to 10 variants in a shared context to take advantage of long context and provider-side cache hits.
- For more than 10 variants, split by chunks of 10 with `start_opencode_variant_tmux.py`; all chunks may run in parallel.
- Parent-agent edits are allowed only as a correction step after reviewing a subagent-produced result.
- Stop and report clearly if initialization, writing, validation, or similarity review fails for any angle.
