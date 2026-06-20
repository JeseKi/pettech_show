#!/usr/bin/env python3
"""Launch opencode variant-writing sessions in tmux, chunked by angle count."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from math import ceil
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "deepseek/deepseek-v4-pro"
DEFAULT_MAX_VARIANTS = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants-dir", required=True, help="variants/ workspace from init_variant_batch.py")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"opencode model. Default {DEFAULT_MODEL}.")
    parser.add_argument(
        "--max-variants-per-session",
        type=int,
        default=DEFAULT_MAX_VARIANTS,
        help=f"Chunk size. Must be <= {DEFAULT_MAX_VARIANTS}. Default {DEFAULT_MAX_VARIANTS}.",
    )
    parser.add_argument("--session-prefix", help="tmux session prefix. Defaults to variant-<output_id>")
    parser.add_argument("--dry-run", action="store_true", help="Render prompts and print launch commands only")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    variants_dir = Path(args.variants_dir)
    if not variants_dir.is_dir():
        raise SystemExit(f"Variants directory not found: {variants_dir}")
    if args.max_variants_per_session < 1 or args.max_variants_per_session > DEFAULT_MAX_VARIANTS:
        raise SystemExit(f"--max-variants-per-session must be between 1 and {DEFAULT_MAX_VARIANTS}")

    manifest = load_json(variants_dir / "manifest.json")
    angle_plan = load_json(variants_dir / "angle_plan.json")
    if not isinstance(angle_plan, list):
        raise SystemExit(f"angle_plan.json must contain a list: {variants_dir / 'angle_plan.json'}")
    if not angle_plan:
        raise SystemExit("No angles found in angle_plan.json")

    output_id = str(manifest.get("output_id") or variants_dir.parent.name)
    session_prefix = args.session_prefix or f"variant-{output_id}"
    session_count = ceil(len(angle_plan) / args.max_variants_per_session)
    prompts_dir = variants_dir / "opencode" / "prompts"
    logs_dir = variants_dir / "opencode" / "logs"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    launched: list[dict[str, Any]] = []
    repo_root = Path.cwd()
    render_script = Path(".agents/skills/wechat-main-variant-batch-rewriter/scripts/render_opencode_variant_prompt.py")

    for index in range(session_count):
        session_index = index + 1
        start = index * args.max_variants_per_session
        limit = min(args.max_variants_per_session, len(angle_plan) - start)
        prompt_file = prompts_dir / f"session-{session_index:02d}.md"
        log_file = logs_dir / f"session-{session_index:02d}.log"
        session_name = f"{session_prefix}-{session_index:02d}"

        subprocess.run(
            [
                "python3",
                render_script.as_posix(),
                "--variants-dir",
                variants_dir.as_posix(),
                "--session-index",
                str(session_index),
                "--start",
                str(start),
                "--limit",
                str(limit),
                "--model",
                args.model,
                "--out",
                prompt_file.as_posix(),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        shell = (
            f"cd {shlex.quote(repo_root.as_posix())} && "
            f"OPENCODE_VARIANT_PROMPT={shlex.quote(prompt_file.as_posix())} "
            'prompt="$(cat "$OPENCODE_VARIANT_PROMPT")" && '
            f"opencode run --model {shlex.quote(args.model)} "
            f"--dir {shlex.quote(repo_root.as_posix())} "
            f"--dangerously-skip-permissions "
            '"$prompt" '
            f"2>&1 | tee {shlex.quote(log_file.as_posix())}"
        )
        tmux_cmd = ["tmux", "new-session", "-d", "-s", session_name, "bash", "-lc", shell]
        launched.append(
            {
                "session": session_name,
                "start": start,
                "limit": limit,
                "prompt_file": prompt_file.as_posix(),
                "log_file": log_file.as_posix(),
                "command": tmux_cmd,
            }
        )
        if not args.dry_run:
            subprocess.run(tmux_cmd, check=True, env=os.environ.copy())

    print(json.dumps({"model": args.model, "sessions": launched}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
