#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f ".env.server" ]; then
  source .env.server
fi

: "${HF_ENDPOINT:=https://hf-mirror.com}"
: "${SUBTWIN_DATA_DIR:=/data/substation-twin}"
: "${SUBTWIN_ALLOW_LOCAL_IMPORT:=1}"
: "${SUBTWIN_DEFAULT_METHOD:=vggt-colmap}"
: "${SUBTWIN_VGGT_REPO:=$ROOT/third_party/vggt}"
: "${SUBTWIN_PYTHON_BIN:=$ROOT/.venv/bin/python}"
: "${HOST:=0.0.0.0}"
: "${PORT:=8000}"

export HF_ENDPOINT
export SUBTWIN_DATA_DIR
export SUBTWIN_ALLOW_LOCAL_IMPORT
export SUBTWIN_DEFAULT_METHOD
export SUBTWIN_VGGT_REPO
export SUBTWIN_PYTHON_BIN

source .venv/bin/activate
exec uvicorn app.main:app --app-dir backend --host "$HOST" --port "$PORT"
