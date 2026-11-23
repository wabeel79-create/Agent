#!/usr/bin/env bash
# Lancement Kapsi-Q (Linux / macOS)
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
[ -f kapsi.env ] || cp kapsi.env.bimcot kapsi.env
PORT=$(grep -E '^KAPSI_PORT=' kapsi.env | cut -d= -f2); PORT=${PORT:-8000}
echo "Kapsi-Q : http://localhost:$PORT"
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
