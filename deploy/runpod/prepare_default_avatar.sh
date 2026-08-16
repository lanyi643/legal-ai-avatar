#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/workspace/legal-ai-avatar}"
VENV_DIR="${VENV_DIR:-/workspace/legal-ai-avatar-venv}"
AVATAR_ID="${AVATAR_ID:-legal_avatar}"
IMAGE="$ROOT_DIR/assets/default-legal-presenter.png"
VIDEO="/workspace/default-legal-presenter.mp4"

[[ -f "$IMAGE" ]] || { echo "缺少默认人物图片：$IMAGE" >&2; exit 1; }
source "$VENV_DIR/bin/activate"

ffmpeg -y -loop 1 -i "$IMAGE" -t 8 -r 25 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=#dedbd6" \
  -pix_fmt yuv420p "$VIDEO"

cd "$ROOT_DIR"
python avatars/musetalk/genavatar.py \
  --file "$VIDEO" \
  --avatar_id "$AVATAR_ID" \
  --save_path data/avatars \
  --version v15 \
  --bbox_shift 0 \
  --extra_margin 10 \
  --parsing_mode jaw

echo "默认数字人已创建：$ROOT_DIR/data/avatars/$AVATAR_ID"
