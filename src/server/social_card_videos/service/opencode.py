# -*- coding: utf-8 -*-
"""OpenCode runner and prompt construction for social card video jobs."""

from __future__ import annotations

from pathlib import Path

from src.server.opencode import run_opencode_in_tmux


def run_opencode(workdir: Path) -> None:
    run_opencode_in_tmux(
        workdir,
        title="Xiaohongshu slideshow video generation",
        prompt=build_prompt(workdir),
    )


def build_prompt(workdir: Path) -> str:
    return f"""
你在一个隔离的小红书轮播视频生成工作目录中工作：{workdir.as_posix()}

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

进度协议：
- 当前目录下必须维护 `progress.json`，并保证它始终是合法 JSON。
- `progress.json` 顶层必须包含 `status`、`current_step`、`events`。
- `events` 必须是数组，每项至少包含 `event`、`step`、`summary`。
- 必须先读取已有 `progress.json` 的 `events` 并在末尾追加新事件；禁止清空、重置或重建已有 `events`。
- 每开始一个步骤，立刻重写 `progress.json`，追加 `开始` 事件，并把 `status` 设为 `running`。
- 如果任务失败，必须把 `status` 设为 `failure`，`current_step` 设为 `任务失败`，并追加 `失败` 事件。
- 全部视频生成和校验完成后，必须把 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。

目标：
1. 读取当前目录下的 `video-config.json`。
2. 如果配置中的 `voice_text` 为空字符串：
   - 先读取 `source/xhs_guizang/main.md`；如果存在多个图文变体，也可参考 `source/xhs_guizang_variants/*/main.md`。
   - 自行生成一段适合中文 TTS 的短配音文案，要求先点出主题/问题，再接一句互动引导。
   - 文案控制在 80-160 个中文字符，避免堆砌整篇正文。
   - 把生成的文案写回 `video-config.json`：单条配置写入顶层 `voice_text`，批量配置写入 `defaults.voice_text`。
3. 使用 $xhs-slideshow-video-maker 的默认脚本生成轮播视频：
   `node .agents/skills/xhs-slideshow-video-maker/scripts/render_slideshow_video.cjs --config video-config.json`
4. 对每个生成的 `video/slideshow.mp4` 运行该 Skill 的验收脚本：
   `.agents/skills/xhs-slideshow-video-maker/scripts/verify_video.sh <mp4路径>`
5. 不要上传视频到任何云服务。
6. 完成后直接结束，不要等待用户继续输入。

要求：
- 使用配置中的 `bgm_source` 和 `bgm_start` 处理用户上传的 BGM 起始点。
- 用户没有填写配音文案时，必须由你生成并写回配置，不能产出静音视频。
- 字幕和顶部标题字体优先使用当前工作目录内 `.agents/assets/fonts/` 下的已授权字体文件，例如 `msyh.ttc`、`msyh.ttf`、`msyhbd.ttc`、`MicrosoftYaHei.ttf`、`NotoSansSC-Regular.otf` 或 `NotoSansSC-Bold.otf`；如果找到可用字体，把相对路径写入 `video-config.json` 的 `font` 字段。
- 不要递归 Glob `/usr/share/fonts` 或任何系统字体目录；如需系统字体，只能用脚本默认候选或 `fc-match`/`fc-list` 查询到的单个字体路径。
- 如果 `video-config.json` 使用批量 `jobs`，必须为每个 job 都生成视频。
- 不要修改 `source/` 中的 PNG 图文卡。
- 如果 TTS 或 ffmpeg/ffprobe 失败，必须在 `progress.json` 和日志中写清楚失败原因。
""".strip()
