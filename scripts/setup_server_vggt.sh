#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${HF_ENDPOINT:=https://hf-mirror.com}"
: "${PYTHON_BIN:=python3}"
: "${VGGT_REPO_URL:=https://github.com/facebookresearch/vggt.git}"
: "${VGGT_MODEL_ID:=facebook/VGGT-1B}"
: "${SUBTWIN_PRELOAD_VGGT:=1}"
: "${CUDA_TORCH_INDEX:=https://download.pytorch.org/whl/cu121}"

export HF_ENDPOINT
export PIP_DISABLE_PIP_VERSION_CHECK=1

echo "[setup] root: $ROOT"
echo "[setup] HF_ENDPOINT=$HF_ENDPOINT"

if [ ! -x ".venv/bin/python" ]; then
  rm -rf .venv
  if ! "$PYTHON_BIN" -m venv .venv; then
    echo "[setup] python venv is unavailable; falling back to virtualenv in user site"
    "$PYTHON_BIN" -m pip install --user virtualenv
    "$PYTHON_BIN" -m virtualenv .venv
  fi
fi

source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

echo "[setup] installing PyTorch from $CUDA_TORCH_INDEX"
pip install torch torchvision --index-url "$CUDA_TORCH_INDEX"

echo "[setup] installing backend dependencies"
pip install -r backend/requirements.txt
pip install pillow plyfile huggingface_hub safetensors opencv-python

mkdir -p third_party
if [ ! -d "third_party/vggt/.git" ]; then
  echo "[setup] cloning VGGT"
  git clone "$VGGT_REPO_URL" third_party/vggt
else
  echo "[setup] updating VGGT"
  git -C third_party/vggt pull --ff-only || true
fi

if [ -f "third_party/vggt/requirements.txt" ]; then
  echo "[setup] installing VGGT requirements"
  pip install -r third_party/vggt/requirements.txt
fi

if [ -f "third_party/vggt/requirements_demo.txt" ]; then
  echo "[setup] installing VGGT demo requirements"
  pip install -r third_party/vggt/requirements_demo.txt
fi

if [ "$SUBTWIN_PRELOAD_VGGT" = "1" ]; then
  echo "[setup] preloading VGGT model from HuggingFace mirror: $VGGT_MODEL_ID"
  python - <<PY
import os
from huggingface_hub import snapshot_download

print("HF_ENDPOINT=", os.environ.get("HF_ENDPOINT"))
path = snapshot_download(repo_id="${VGGT_MODEL_ID}")
print("VGGT_MODEL_CACHE=", path)
PY
fi

if command -v npm >/dev/null 2>&1; then
  echo "[setup] installing frontend dependencies"
  (cd frontend && npm install)
else
  echo "[setup] npm not found; install Node.js 18+ before running the frontend"
fi

cat > .env.server <<EOF
export HF_ENDPOINT=$HF_ENDPOINT
export SUBTWIN_DATA_DIR=${SUBTWIN_DATA_DIR:-/data/substation-twin}
export SUBTWIN_ALLOW_LOCAL_IMPORT=1
export SUBTWIN_DEFAULT_METHOD=vggt-colmap
export SUBTWIN_VGGT_REPO=$ROOT/third_party/vggt
export SUBTWIN_PYTHON_BIN=$ROOT/.venv/bin/python
export VGGT_MODEL_ID=$VGGT_MODEL_ID
EOF

echo "[setup] done"
echo "[setup] next:"
echo "  source .venv/bin/activate"
echo "  source .env.server"
echo "  bash scripts/start_backend.sh"
