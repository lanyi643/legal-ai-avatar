#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/workspace/legal-ai-avatar}"
export ROOT_DIR
MODEL_DIR="$ROOT_DIR/models"
mkdir -p "$MODEL_DIR/musetalkV15" "$MODEL_DIR/sd-vae" "$MODEL_DIR/whisper" \
  "$MODEL_DIR/dwpose" "$MODEL_DIR/syncnet" "$MODEL_DIR/face-parse-bisent"

hf download TMElyralab/MuseTalk \
  --local-dir "$MODEL_DIR" \
  --include "musetalkV15/musetalk.json" "musetalkV15/unet.pth"
hf download stabilityai/sd-vae-ft-mse \
  --local-dir "$MODEL_DIR/sd-vae" \
  --include "config.json" "diffusion_pytorch_model.bin"
hf download openai/whisper-tiny \
  --local-dir "$MODEL_DIR/whisper" \
  --include "config.json" "pytorch_model.bin" "preprocessor_config.json"
hf download yzd-v/DWPose \
  --local-dir "$MODEL_DIR/dwpose" \
  --include "dw-ll_ucoco_384.pth"
hf download ByteDance/LatentSync \
  --local-dir "$MODEL_DIR/syncnet" \
  --include "latentsync_syncnet.pt"

python -m gdown 154JgKpzCPW82qINcVieuPH3fZ2e0P812 \
  -O "$MODEL_DIR/face-parse-bisent/79999_iter.pth"
python - <<'PY'
import os
from pathlib import Path
from urllib.request import urlretrieve

target = Path(os.environ["ROOT_DIR"]) / "models/face-parse-bisent/resnet18-5c106cde.pth"
urlretrieve("https://download.pytorch.org/models/resnet18-5c106cde.pth", target)
print(target)
PY

echo "MuseTalk 模型下载完成：$MODEL_DIR"
