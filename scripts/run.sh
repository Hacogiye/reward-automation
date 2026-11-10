#!/usr/bin/env sh
# Mở giao diện PrixAuto (Linux / macOS). Chạy tự động không giao diện: scripts/run.sh --run-all --headless
cd "$(dirname "$0")/.." || exit 1
exec python3 -m rewards_bot "$@"
