#!/usr/bin/env sh
# Chạy toàn bộ test (logic, dữ liệu, giao diện). Chạy trước mỗi lần commit.
cd "$(dirname "$0")/.." || exit 1
# có .venv thì dùng Python trong đó, không thì dùng python3 của máy
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
if "$PY" -m pytest -q tests "$@"; then
  echo "Tat ca test deu dat."
else
  echo
  echo "CO TEST LOI - chua nen commit."
  exit 1
fi
