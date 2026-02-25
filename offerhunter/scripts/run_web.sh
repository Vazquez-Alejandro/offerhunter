#!/usr/bin/env bash
set -euo pipefail

# Cloud platforms (Railway/Render/Fly) provide PORT. Locally defaults to 8501.
PORT="${PORT:-8501}"

exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="$PORT"
