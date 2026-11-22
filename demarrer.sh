#!/usr/bin/env bash
# Lancement Kapsi-Q (Linux / macOS)
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
[ -f data/kapsi_q.db ] || python3 -m app.demo
echo "Kapsi-Q : http://localhost:8000"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
