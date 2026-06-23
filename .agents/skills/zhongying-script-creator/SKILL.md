---
name: zhongying-script-creator
description: Generate Zhongying shootable script creation results for script-creation capability jobs. Use when asked to create master scripts, viral-template adaptations, warm healing scripts, professional authority scripts, lively humorous scripts, or humanized script rewrites from local input/inputs.json and write validated output/result.md plus output/result.json.
---

# Zhongying Script Creator

Generate a validated shootable script result for a Zhongying capability job workspace.

## Workflow

1. Work only inside the current task workspace.
2. Read `input/inputs.json`.
3. Use the requested capability key and title from the user prompt to choose the script style.
4. Create `output/result.md` as a readable script report.
5. Create `output/result.json` as strict JSON. Use a JSON writer when possible.
6. Run:

   ```bash
   python3 .agents/skills/zhongying-script-creator/scripts/validate_result.py --workdir . --capability-key <capability_key>
   ```

7. If validation fails, fix the files and rerun validation until it passes.

## Output Contract

`output/result.json` must be a JSON object with these top-level fields:

- `title`: string
- `capability_key`: exact capability key from the task
- `summary`: object
- `sections`: non-empty array of objects
- `next_actions`: non-empty array

It must also contain one of:

- `scenes`: non-empty array of scene objects
- `script`: object containing shootable script content

Each scene should include practical production information, such as:

- `scene` or `title`
- `visual` or `shot`
- `voiceover` or `dialogue`
- `duration`
- `notes`

## Rules

- Prefer Chinese corner quotes such as `「」` inside JSON string values. Do not place raw ASCII quotes inside JSON strings unless they are escaped.
- Do not include Markdown fences in `result.json`.
- Do not use `Demo` as a capability name or title.
- Keep scripts practical: include opening hook, body beats, camera/visual guidance, and closing action.
- Do not invent medical guarantees, pricing, platform metrics, or factual claims not supported by the input.
- Keep `result.md` reader-facing; do not mention prompt engineering, local file paths, or validation internals.
