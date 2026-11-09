@echo off
rem Nhấp đúp để mở giao diện PrixAuto
cd /d "%~dp0"
python -m rewards_bot %*
if errorlevel 1 pause
