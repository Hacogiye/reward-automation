#!/usr/bin/env sh
# Mở giao diện PrixAuto (Linux / macOS). Chạy tự động không giao diện: scripts/run.sh --run-all --headless
cd "$(dirname "$0")/.." || exit 1
# có .venv thì dùng Python trong đó, không thì dùng python3 của máy
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec "$PY" -m rewards_bot "$@"
