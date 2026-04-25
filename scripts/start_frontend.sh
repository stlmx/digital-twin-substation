#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

API_BASE="${1:-${VITE_API_BASE:-http://localhost:8000}}"
export VITE_API_BASE="$API_BASE"

exec npm run dev -- --host 0.0.0.0 --port "${PORT:-5173}"
