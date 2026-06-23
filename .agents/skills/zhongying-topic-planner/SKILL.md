---
name: zhongying-topic-planner
description: Generate Zhongying content topic planning results for topic-planning capability jobs. Use when asked to create pain-point, gap, crossover, counterintuitive, trend, festival, controversy, series, or seasonal topic pools from local input/inputs.json and write validated output/result.md plus output/result.json.
---

# Zhongying Topic Planner

Generate a validated topic planning result for a Zhongying capability job workspace.

## Workflow

1. Work only inside the current task workspace.
2. Read `input/inputs.json`.
3. Use the requested capability key and title from the user prompt to choose the topic method.
4. Create `output/result.md` as a concise Markdown report.
5. Create `output/result.json` as strict JSON. Do not hand-write invalid JSON; use a JSON writer when possible.
6. Run:

   ```bash
   python3 .agents/skills/zhongying-topic-planner/scripts/validate_result.py --workdir . --capability-key <capability_key>
   ```

7. If validation fails, fix the files and rerun validation until it passes.

## Output Contract

`output/result.json` must be a JSON object with these top-level fields:

- `title`: string
- `capability_key`: exact capability key from the task
- `summary`: object
- `sections`: non-empty array of objects
- `topics`: non-empty array of topic objects
- `next_actions`: non-empty array

Each item in `topics` must include:

- `title`: topic title
- `category`: topic category
- `total_score`: numeric score
- `recommended_hook`: hook or opening angle

Recommended optional topic fields:

- `target_audience`
- `content_outline`
- `advantages_used`
- `avoid_check`
- `priority`
- `publishing_note`

## Rules

- Prefer Chinese corner quotes such as `「」` inside JSON string values. Do not place raw ASCII quotes inside JSON strings unless they are escaped.
- Do not include Markdown fences in `result.json`.
- Do not use `Demo` as a capability name or title.
- Do not invent medical guarantees, pricing, platform metrics, or factual claims not supported by the input.
- Keep `result.md` reader-facing; do not mention prompt engineering, local file paths, or validation internals.
