#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/workspace/legal-ai-avatar}"
VENV_DIR="${VENV_DIR:-/workspace/legal-ai-avatar-venv}"
AVATAR_ID="${AVATAR_ID:-legal_avatar}"
APP_USER="${APP_USER:-legal}"

if [[ -z "${APP_PASSWORD:-}" ]]; then
  echo "请先设置 APP_PASSWORD，例如：export APP_PASSWORD='至少16位随机密码'" >&2
  exit 1
fi

required=(
  "$ROOT_DIR/models/musetalkV15/unet.pth"
  "$ROOT_DIR/models/musetalkV15/musetalk.json"
  "$ROOT_DIR/models/sd-vae/config.json"
  "$ROOT_DIR/models/whisper/config.json"
)
for file in "${required[@]}"; do
  [[ -f "$file" ]] || { echo "缺少模型文件：$file" >&2; exit 1; }
done

source "$VENV_DIR/bin/activate"
cd "$ROOT_DIR"
mkdir -p /workspace/legal-avatar-outputs /workspace/legal-avatar-logs

python app.py --transport webrtc --model musetalk --avatar_id "$AVATAR_ID" --listenport 8010 \
  > /workspace/legal-avatar-logs/engine.log 2>&1 &
ENGINE_PID=$!
trap 'kill "$ENGINE_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 120); do
  if curl -fsS http://127.0.0.1:8010/ >/dev/null 2>&1; then break; fi
  if ! kill -0 "$ENGINE_PID" 2>/dev/null; then
    tail -n 100 /workspace/legal-avatar-logs/engine.log >&2
    exit 1
  fi
  sleep 2
done

export LIVETALKING_URL=http://127.0.0.1:8010
export OUTPUT_DIR=/workspace/legal-avatar-outputs
export APP_USER APP_PASSWORD
exec uvicorn legal_mvp.app:app --host 0.0.0.0 --port 7860
