# TTS 和 BGM 参考

## 中文 TTS

默认外部 TTS 接口：

```bash
curl -G --fail \
  --data-urlencode "text=这里是一句旁白" \
  "https://api.milorapart.top/apis/mbAIsc" \
  -o /tmp/voice.json

URL=$(node -e "const fs=require('fs'); const r=JSON.parse(fs.readFileSync('/tmp/voice.json','utf8')); process.stdout.write(r.url)")
curl -L --fail "$URL" -o voice.mp3
```

中文文案必须用 `--data-urlencode` 传参，避免 URL 编码错误导致发音异常或接口失败。

如果测试时接口证书过期，可以在渲染配置里设置 `"tts_insecure": true`，脚本会给 `curl` 加 `-k`。这种情况要写入任务备注，方便之后审计。

如果 TTS 服务不可用，不要伪造音频。可以改用用户提供的本地 `voice_audio`，或者向用户确认新的 TTS 提供方。

## 批量配音顺序

批量生成同一主题的多个视觉变体时，默认只生成一次配音，然后所有视频复用这一份音频。这样可以避免重复调用接口，也避免不同变体之间出现音色、语速或停顿细节不一致。

推荐做法：

- 把共享配音文案放到 `defaults.voice_text`。
- 如果已经有本地配音，把路径放到 `defaults.voice_audio`。
- 如果需要脚本生成配音，不要在每个 job 里重复写 `voice_text`。
- 只有某个视频需要特殊旁白时，才在该 job 里覆盖 `voice_text` 或 `voice_audio`。

## BGM

优先使用本地、已授权或用户提供的 BGM。用户明确要求下载某首歌时，要记录来源 URL；除非已经核验授权，否则要注明版权未核验。

渲染脚本支持：

- `bgm_audio`：已经准备好的本地音频文件。
- `bgm_source` + `bgm_start`：从源音频中裁剪一段，输出到 `<output_dir>/video/bgm-crop.mp3`。

推荐默认值：

- 配音音量：`1.12`
- BGM 音量：`0.22`
- 配音延迟：`0.5` 秒
- BGM 时长：与视频时长一致

脚本会在存在配音文件时用 `ffprobe` 读取真实配音时长，并据此安排字幕时间。
