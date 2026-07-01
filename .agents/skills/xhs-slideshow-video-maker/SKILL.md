---
name: xhs-slideshow-video-maker
description: 把本地小红书/Rednote 图文卡片批量生成竖屏轮播短视频。适用于把本地小红书卡片 PNG/JPG 输出转成短视频风格 MP4，并自动加入顶部常驻标题、黄字黑边大字幕、中文 TTS 配音、可选 BGM、video.md 引用和 ffprobe/抽帧验收。
---

# 小红书轮播视频生成器

## 概览

使用这个 Skill，把已经生成好的小红书图文卡片转成竖屏短视频式轮播。默认成片规格为 `1080x1440`，顶部常驻黄字黑边标题，底部显示黄字黑边大字幕，配音先点题再接 hook，可选低音量 BGM。

## 工作流程

1. 准备输入：

- `image_dir`：有序卡片图片目录，支持 `.png`、`.jpg`、`.jpeg`、`.webp`。
- `output_dir`：输出目录，脚本会写入 `video/slideshow.mp4`、overlay、配音文件和 `video.md`。
- `title`：顶部常驻标题，建议 1-2 行。
- `voice_text`：配音文案。文章类 hook 要先点出主题/问题，再接引导语。
- 可选 `bgm_audio`，或者 `bgm_source` + `bgm_start`。

2. 在目标卡片目录旁创建配置 JSON。

单条视频示例：

```json
{
  "image_dir": "/abs/path/xhs_guizang/output",
  "output_dir": "/abs/path/xhs_guizang",
  "title": "药食同源轻创业\n新手照着流程做",
  "voice_text": "普通人到底能不能做药食同源轻创业？人人都关注健康，药食同源，不缺市场，只是很多人还没有看懂而已。点个小红心打药膳，咱们评论区聊一聊。",
  "bgm_audio": "/abs/path/xhs_video_assets/ruoshui-climax.mp3",
  "write_video_md": true
}
```

批量视频示例：

```json
{
  "defaults": {
    "title": "药食同源轻创业\n新手照着流程做",
    "voice_text": "普通人到底能不能做药食同源轻创业？人人都关注健康，药食同源，不缺市场，只是很多人还没有看懂而已。点个小红心打药膳，咱们评论区聊一聊。",
    "bgm_audio": "/abs/path/xhs_video_assets/ruoshui-climax.mp3",
    "write_video_md": true
  },
  "jobs": [
    {
      "label": "xhs_guizang",
      "image_dir": "/abs/path/xhs_guizang/output",
      "output_dir": "/abs/path/xhs_guizang"
    },
    {
      "label": "variant-01",
      "image_dir": "/abs/path/xhs_guizang_variants/variant-01/output",
      "output_dir": "/abs/path/xhs_guizang_variants/variant-01"
    }
  ]
}
```

批量模式下，把共享的 `voice_text`、`voice_audio`、BGM 配置放在 `defaults`。如果 `defaults.voice_text` 存在且 `defaults.voice_audio` 不存在，脚本会先在共享目录生成一次 TTS，再把同一个音频复用到每个视频。共享目录由 `shared_asset_dir` 指定，默认是配置文件旁边的 `xhs_video_assets`。只有某个视频确实需要不同配音时，才在单个 job 里覆盖 `voice_text` 或 `voice_audio`。

3. 生成视频。

```bash
node /Users/Admin/Projects/DailyWriting/.agents/skills/xhs-slideshow-video-maker/scripts/render_slideshow_video.cjs --config /abs/path/video-config.json
```

4. 验收视频。

```bash
/Users/Admin/Projects/DailyWriting/.agents/skills/xhs-slideshow-video-maker/scripts/verify_video.sh /abs/path/xhs_guizang/video/slideshow.mp4
```

检查抽帧图片时重点看：

- 顶部标题是否全程在上方留白/元信息区域，不遮挡主体内容；
- 字幕是否按短句展示，没有把整段话堆在一起；
- 黄字黑边在浅色和深色卡片上都清楚；
- 视频是否同时包含视频流和音频流。

## 必须保留的默认规则

- 默认输出 `1080x1440`、`30fps`、H.264 视频和 AAC 音频。
- 顶部标题全程常驻。
- 标题和字幕都使用黄字黑边。
- 字幕要大，按中文标点和短语自动断句。
- 视频放在 `<output_dir>/video/slideshow.mp4`。
- 视频引用写入 `<output_dir>/video.md`；图片引用仍保留在 `main.md`。
- 文章类 hook 的配音文案要先点题，再接 hook。
- 批量生成视频时，先生成一次共享配音，再复用到所有视觉变体。

## 字体规则

- 中文标题和字幕优先使用 `.agents/assets/fonts/` 下的已授权字体文件，常见文件名包括 `msyh.ttc`、`msyh.ttf`、`msyhbd.ttc`、`MicrosoftYaHei.ttf`。
- 如果配置 JSON 手动设置 `font`，脚本会优先使用该路径；否则会自动尝试项目字体目录，再尝试少量固定系统候选。
- 不要递归 Glob `/usr/share/fonts` 或任何系统字体目录。如果项目字体和固定候选都不可用，应明确报错提示设置 `config.font`。

## 脚本

- `scripts/render_slideshow_video.cjs`：读取单条或批量 JSON 配置，生成或复用配音，裁剪 BGM，调用 overlay 生成和 ffmpeg 合成，并写 `video.md`。
- `scripts/render_text_overlays.py`：用 Pillow 生成透明 PNG 标题层和字幕层。
- `scripts/verify_video.sh`：用 ffprobe 检查视频规格，并抽取关键帧。

## TTS 和 BGM

当需要新生成配音或处理 BGM，而不是直接使用本地音频文件时，再读取 `references/tts-and-bgm.md`。
