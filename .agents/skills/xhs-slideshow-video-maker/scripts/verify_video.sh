#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /abs/path/video.mp4 [output-frame-dir]" >&2
  exit 2
fi

VIDEO="$1"
OUT_DIR="${2:-$(dirname "$VIDEO")/verify_frames}"

if [[ ! -f "$VIDEO" ]]; then
  echo "Video not found: $VIDEO" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "== ffprobe =="
ffprobe -v error \
  -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels \
  -show_entries format=duration \
  -of default=noprint_wrappers=1 \
  "$VIDEO"

echo "== frames =="
for point in 0.8 3.2 12.4; do
  out="$OUT_DIR/frame_${point//./_}.jpg"
  ffmpeg -y -v error -ss "$point" -i "$VIDEO" -frames:v 1 -update 1 "$out"
  echo "$out"
done
