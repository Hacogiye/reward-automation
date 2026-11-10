@echo off
rem Chạy toàn bộ test (logic, dữ liệu, giao diện). Chạy trước mỗi lần commit.
cd /d "%~dp0.."
python -m pytest -q tests %*
if errorlevel 1 (
  echo.
  echo CO TEST LOI - chua nen commit.
  exit /b 1
)
echo Tat ca test deu dat.
