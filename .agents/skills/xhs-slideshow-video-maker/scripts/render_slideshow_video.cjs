#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const SCRIPT_DIR = __dirname;
const OVERLAY_SCRIPT = path.join(SCRIPT_DIR, 'render_text_overlays.py');

function usage() {
  console.error('Usage: render_slideshow_video.cjs --config /abs/path/config.json');
  process.exit(2);
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === '--config') {
      args.config = argv[i + 1];
      i += 1;
    } else {
      usage();
    }
  }
  if (!args.config) usage();
  return args;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: options.stdio || 'inherit', encoding: 'utf8' });
  if (result.status !== 0) {
    throw new Error(`${command} failed with exit code ${result.status}`);
  }
  return result;
}

function runCapture(command, args) {
  const result = spawnSync(command, args, { encoding: 'utf8' });
  if (result.status !== 0) {
    const stderr = result.stderr ? `\n${result.stderr}` : '';
    throw new Error(`${command} failed with exit code ${result.status}${stderr}`);
  }
  return result.stdout.trim();
}

function absMaybe(file, baseDir) {
  if (!file) return file;
  return path.isAbsolute(file) ? file : path.resolve(baseDir, file);
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, data) {
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
}

function shQuoteForConcat(file) {
  return file.replace(/'/g, "'\\''");
}

function splitChineseText(text) {
  const normalized = String(text || '')
    .replace(/\s+/g, '')
    .replace(/[；;，,]/g, '，')
    .replace(/[。！？!?]/g, (m) => `${m}\n`);
  const rough = normalized
    .split(/\n|，|、/)
    .map((part) => part.trim())
    .filter(Boolean);

  const pieces = [];
  for (const part of rough) {
    if (part.length <= 22) {
      pieces.push(part);
      continue;
    }
    let cursor = 0;
    while (cursor < part.length) {
      pieces.push(part.slice(cursor, cursor + 20));
      cursor += 20;
    }
  }
  return pieces;
}

function wrapSubtitle(text) {
  const value = String(text);
  if (value.length <= 11 || value.includes('\n')) return value;
  const preferredBreaks = ['？', '?', '，', ',', '做', '是', '不'];
  for (const marker of preferredBreaks) {
    const index = value.indexOf(marker);
    if (index >= 5 && index <= value.length - 5) {
      const splitAt = index + 1;
      return `${value.slice(0, splitAt)}\n${value.slice(splitAt)}`;
    }
  }
  const midpoint = Math.ceil(value.length / 2);
  return `${value.slice(0, midpoint)}\n${value.slice(midpoint)}`;
}

function imageFiles(job) {
  const imageDir = job.image_dir;
  const prefix = job.image_prefix || '';
  const exts = new Set(['.png', '.jpg', '.jpeg', '.webp']);
  return fs.readdirSync(imageDir)
    .filter((name) => exts.has(path.extname(name).toLowerCase()))
    .filter((name) => !prefix || name.startsWith(prefix))
    .sort((a, b) => a.localeCompare(b, 'en', { numeric: true }))
    .map((name) => path.join(imageDir, name));
}

function writeConcatList(files, listPath, slideSeconds) {
  const lines = [];
  for (const file of files) {
    lines.push(`file '${shQuoteForConcat(file)}'`);
    lines.push(`duration ${Number(slideSeconds).toFixed(3)}`);
  }
  lines.push(`file '${shQuoteForConcat(files[files.length - 1])}'`);
  fs.writeFileSync(listPath, `${lines.join('\n')}\n`, 'utf8');
}

function ffprobeDuration(file) {
  const out = runCapture('ffprobe', [
    '-v', 'error',
    '-show_entries', 'format=duration',
    '-of', 'default=noprint_wrappers=1:nokey=1',
    file,
  ]);
  const value = Number(out);
  return Number.isFinite(value) ? value : 0;
}

function generateTts(job, videoDir) {
  if (job.voice_audio) return absMaybe(job.voice_audio, job.base_dir);
  if (job.generate_tts === false) return null;
  const voiceText = String(job.voice_text || '').trim();
  if (!voiceText) return null;

  const endpoint = job.tts_endpoint || 'https://api.milorapart.top/apis/mbAIsc';
  const jsonPath = path.join(videoDir, 'voice-response.json');
  const voicePath = path.join(videoDir, 'voice.mp3');
  const curlBase = ['--fail'];
  if (job.tts_insecure) curlBase.push('-k');

  run('curl', [
    '-G',
    ...curlBase,
    '--data-urlencode', `text=${voiceText}`,
    endpoint,
    '-o', jsonPath,
  ]);

  const response = readJson(jsonPath);
  const audioUrl = response.url || response.data?.url || response.audio || response.mp3;
  if (!audioUrl) {
    throw new Error(`TTS response did not contain an audio URL: ${jsonPath}`);
  }

  run('curl', [
    '-L',
    ...curlBase,
    audioUrl,
    '-o', voicePath,
  ]);
  return voicePath;
}

function cropBgm(job, videoDir, duration) {
  if (job.bgm_audio) return absMaybe(job.bgm_audio, job.base_dir);
  if (!job.bgm_source) return null;
  const bgmSource = absMaybe(job.bgm_source, job.base_dir);
  const out = path.join(videoDir, 'bgm-crop.mp3');
  run('ffmpeg', [
    '-y',
    '-ss', String(job.bgm_start || 0),
    '-t', String(job.bgm_duration || Math.max(duration + 2, duration)),
    '-i', bgmSource,
    '-c:a', 'libmp3lame',
    '-b:a', '192k',
    out,
  ]);
  return out;
}

function makeSubtitleTimings(subtitles, job, voiceDuration, videoDuration) {
  const start = Number(job.subtitle_start ?? 0.45);
  const desiredEnd = voiceDuration > 0
    ? Number(job.voice_delay ?? 0.5) + voiceDuration + 0.2
    : videoDuration - 0.4;
  const end = Math.min(Number(job.subtitle_end ?? desiredEnd), videoDuration - 0.2);
  const available = Math.max(1, end - start);
  const weights = subtitles.map((text) => Math.max(String(text).replace(/\n/g, '').length, 4));
  const total = weights.reduce((sum, value) => sum + value, 0) || 1;

  let cursor = start;
  return subtitles.map((subtitle, index) => {
    const rawDuration = available * (weights[index] / total);
    const duration = Math.max(0.9, Math.min(2.4, rawDuration));
    const item = {
      file: `subtitle-${String(index + 1).padStart(2, '0')}.png`,
      start: cursor,
      end: Math.min(cursor + duration, videoDuration - 0.1),
    };
    cursor = item.end;
    return item;
  });
}

function renderOverlays(job, videoDir, subtitles) {
  const overlayDir = path.join(videoDir, 'overlays');
  ensureDir(overlayDir);
  const overlayConfigPath = path.join(videoDir, 'overlay-config.json');
  const overlayConfig = {
    width: Number(job.width || 1080),
    height: Number(job.height || 1440),
    title: job.title || '',
    subtitles,
    fill: job.text_fill || '#FFDA00',
    stroke_fill: job.text_stroke_fill || '#000000',
    title_font_size: Number(job.title_font_size || 66),
    title_y: Number(job.title_y || 104),
    title_stroke: Number(job.title_stroke || 7),
    title_max_width: Number(job.title_max_width || 980),
    subtitle_font_size: Number(job.subtitle_font_size || 82),
    subtitle_y: Number(job.subtitle_y || 1150),
    subtitle_stroke: Number(job.subtitle_stroke || 8),
    subtitle_max_width: Number(job.subtitle_max_width || 980),
  };
  if (job.font) overlayConfig.font = absMaybe(job.font, job.base_dir);
  writeJson(overlayConfigPath, overlayConfig);
  run('python3', [OVERLAY_SCRIPT, '--config', overlayConfigPath, '--output-dir', overlayDir]);
  return overlayDir;
}

function buildAudioFilter(job, hasVoice, hasBgm, videoDuration) {
  if (hasVoice && hasBgm) {
    return [
      `[2:a]volume=${Number(job.bgm_volume ?? 0.22)},atrim=0:${videoDuration},asetpts=PTS-STARTPTS[bgm]`,
      `[1:a]adelay=${Math.round(Number(job.voice_delay ?? 0.5) * 1000)}|${Math.round(Number(job.voice_delay ?? 0.5) * 1000)},volume=${Number(job.voice_volume ?? 1.12)},apad,atrim=0:${videoDuration},asetpts=PTS-STARTPTS[voice]`,
      '[bgm][voice]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95[a]',
    ];
  }
  if (hasVoice) {
    return [
      `[1:a]adelay=${Math.round(Number(job.voice_delay ?? 0.5) * 1000)}|${Math.round(Number(job.voice_delay ?? 0.5) * 1000)},volume=${Number(job.voice_volume ?? 1.12)},apad,atrim=0:${videoDuration},asetpts=PTS-STARTPTS,alimiter=limit=0.95[a]`,
    ];
  }
  if (hasBgm) {
    return [
      `[1:a]volume=${Number(job.bgm_volume ?? 0.22)},atrim=0:${videoDuration},asetpts=PTS-STARTPTS,alimiter=limit=0.95[a]`,
    ];
  }
  return [
    `anullsrc=channel_layout=stereo:sample_rate=48000,atrim=0:${videoDuration}[a]`,
  ];
}

function writeVideoMd(job, outputDir, videoPath, voicePath, bgmPath) {
  if (job.write_video_md === false) return;
  const rel = (file) => path.relative(outputDir, file).split(path.sep).join('/');
  const lines = [
    `# ${job.label || '小红书轮播'}视频版`,
    '',
    '## 视频',
    '',
    `[本地视频：slideshow.mp4](${rel(videoPath)})`,
    '',
    '## 音频',
    '',
    voicePath ? `- 配音：本地文件 \`${rel(voicePath)}\`` : '- 配音：未配置，使用静音轨。',
    job.voice_text ? `- 配音文案：${job.voice_text}` : '- 配音文案：未配置。',
    bgmPath ? `- BGM：本地文件 \`${rel(bgmPath)}\`` : '- BGM：未配置。',
    '- 字幕：已烧录到视频画面，黄字黑边大字号，按短句逐条出现。',
    '- 标题：已全程烧录在视频顶部留白区，黄字黑边粗体。',
    '- 上传：未执行；本文件仅引用本地视频。'
  ];
  fs.writeFileSync(path.join(outputDir, 'video.md'), `${lines.join('\n')}\n`, 'utf8');
}

function renderJob(rawJob, configDir) {
  const job = { ...rawJob };
  job.base_dir = configDir;
  job.image_dir = absMaybe(job.image_dir, configDir);
  job.output_dir = absMaybe(job.output_dir, configDir);
  if (!job.image_dir || !job.output_dir) {
    throw new Error('Each job requires image_dir and output_dir.');
  }

  const outputDir = job.output_dir;
  const videoDir = path.join(outputDir, 'video');
  ensureDir(videoDir);

  const files = imageFiles(job);
  if (!files.length) {
    throw new Error(`${job.label || outputDir}: no image files found in ${job.image_dir}`);
  }

  const slideSeconds = Number(job.slide_seconds || 2.6);
  const listPath = path.join(videoDir, 'slides.txt');
  writeConcatList(files, listPath, slideSeconds);

  const voicePath = generateTts(job, videoDir);
  const voiceDuration = voicePath ? ffprobeDuration(voicePath) : 0;
  const minimumDuration = Math.max(files.length * slideSeconds, voiceDuration + Number(job.voice_delay ?? 0.5) + 1);
  const videoDuration = Number(job.video_duration || minimumDuration.toFixed(1));
  const bgmPath = cropBgm(job, videoDir, videoDuration);

  const subtitles = (job.subtitles && job.subtitles.length ? job.subtitles : splitChineseText(job.voice_text || ''))
    .map(wrapSubtitle);
  const overlayDir = renderOverlays(job, videoDir, subtitles);

  const overlays = [
    { file: 'title.png', start: 0, end: videoDuration },
    ...makeSubtitleTimings(subtitles, job, voiceDuration, videoDuration),
  ];
  const existingOverlays = overlays.filter((overlay) => fs.existsSync(path.join(overlayDir, overlay.file)));

  const width = Number(job.width || 1080);
  const height = Number(job.height || 1440);
  const fps = Number(job.fps || 30);
  const overlayInputs = existingOverlays.flatMap((overlay) => ['-loop', '1', '-i', path.join(overlayDir, overlay.file)]);

  const overlayFilters = [];
  let lastVideo = 'base';
  existingOverlays.forEach((overlay, index) => {
    const inputIndex = 1 + (voicePath ? 1 : 0) + (bgmPath ? 1 : 0) + index;
    const outLabel = `ov${index}`;
    overlayFilters.push(
      `[${lastVideo}][${inputIndex}:v]overlay=0:0:enable='between(t,${overlay.start.toFixed(3)},${overlay.end.toFixed(3)})'[${outLabel}]`
    );
    lastVideo = outLabel;
  });

  const filter = [
    `[0:v]fps=${fps},scale=${width}:${height}:force_original_aspect_ratio=decrease,` +
      `pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2,format=rgba[base]`,
    ...overlayFilters,
    `[${lastVideo}]format=yuv420p[v]`,
    ...buildAudioFilter(job, Boolean(voicePath), Boolean(bgmPath), videoDuration),
  ].join(';');

  const inputs = [
    '-f', 'concat',
    '-safe', '0',
    '-i', listPath,
  ];
  if (voicePath) inputs.push('-i', voicePath);
  if (bgmPath) inputs.push('-stream_loop', '-1', '-i', bgmPath);

  const outPath = path.join(videoDir, 'slideshow.mp4');
  console.log(`Rendering ${job.label || outputDir}`);
  run('ffmpeg', [
    '-y',
    ...inputs,
    ...overlayInputs,
    '-filter_complex', filter,
    '-map', '[v]',
    '-map', '[a]',
    '-t', String(videoDuration),
    '-c:v', 'libx264',
    '-preset', job.preset || 'medium',
    '-crf', String(job.crf || 20),
    '-r', String(fps),
    '-pix_fmt', 'yuv420p',
    '-c:a', 'aac',
    '-b:a', String(job.audio_bitrate || '192k'),
    '-movflags', '+faststart',
    outPath,
  ]);

  writeVideoMd(job, outputDir, outPath, voicePath, bgmPath);
  return { outPath, files: files.length, subtitles: subtitles.length, duration: videoDuration };
}

function prepareSharedAssets(config, configDir) {
  if (!config.jobs || !config.defaults) return config;

  const defaults = { ...config.defaults, base_dir: configDir };
  const shouldShareVoice = defaults.voice_text
    && !defaults.voice_audio
    && defaults.generate_tts !== false
    && config.jobs.length > 1;

  if (!shouldShareVoice) return config;

  const sharedDir = absMaybe(
    config.shared_asset_dir || defaults.shared_asset_dir || 'xhs_video_assets',
    configDir,
  );
  ensureDir(sharedDir);
  console.log(`Generating shared voice for ${config.jobs.length} jobs`);
  const sharedVoice = generateTts(defaults, sharedDir);

  return {
    ...config,
    defaults: {
      ...config.defaults,
      voice_audio: sharedVoice,
    },
  };
}

function main() {
  const args = parseArgs(process.argv);
  const configPath = path.resolve(args.config);
  const configDir = path.dirname(configPath);
  const config = prepareSharedAssets(readJson(configPath), configDir);
  const defaults = config.defaults || {};
  const jobs = config.jobs
    ? config.jobs.map((job) => {
      const merged = { ...defaults, ...job };
      const hasOwnVoiceAudio = Object.prototype.hasOwnProperty.call(job, 'voice_audio');
      if (job.voice_text && job.voice_text !== defaults.voice_text && !hasOwnVoiceAudio) {
        delete merged.voice_audio;
      }
      return merged;
    })
    : [config];

  const results = jobs.map((job) => renderJob(job, configDir));
  console.log(JSON.stringify({ videos: results }, null, 2));
}

main();
