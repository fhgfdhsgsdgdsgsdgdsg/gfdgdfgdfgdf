#!/usr/bin/env bash
# Assemble rendered frames (build/render/<view>/frame_####.png) into preview videos.
# Each video shows the 5 s loop twice so the seam is visible in the clip.
set -euo pipefail
cd "$(dirname "$0")/.."
FPS=30
OUT=preview
mkdir -p "$OUT"
for view in front rear_left right_side; do
  ffmpeg -y -loglevel error -stream_loop 1 -framerate "$FPS" -i "build/render/$view/frame_%04d.png" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart "$OUT/$view.mp4"
done
ffmpeg -y -loglevel error -i "$OUT/front.mp4" -i "$OUT/rear_left.mp4" -i "$OUT/right_side.mp4" \
  -filter_complex "[0:v][1:v][2:v]hstack=inputs=3" \
  -c:v libx264 -pix_fmt yuv420p -crf 20 -movflags +faststart "$OUT/thompson_idle_3views.mp4"
echo "wrote $OUT/{front,rear_left,right_side,thompson_idle_3views}.mp4"
