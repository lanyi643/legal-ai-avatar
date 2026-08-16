#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/workspace/legal-ai-avatar}"
VENV_DIR="${VENV_DIR:-/workspace/legal-ai-avatar-venv}"

if ! command -v nvidia-smi >/dev/null; then
  echo "未检测到 NVIDIA GPU；请确认创建的是 GPU Pod。" >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ffmpeg fonts-noto-cjk git libgl1 libglib2.0-0 python3-venv

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip wheel setuptools
python -m pip install torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 \
  --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r "$ROOT_DIR/requirements.txt"
python -m pip install -r "$ROOT_DIR/legal_mvp/requirements.txt" huggingface_hub gdown

ROOT_DIR="$ROOT_DIR" bash "$ROOT_DIR/deploy/runpod/download_models.sh"
python -m py_compile "$ROOT_DIR/legal_mvp/app.py"
nvidia-smi
echo "安装完成。下一步运行 deploy/runpod/start.sh"
