"""Điểm vào của bản đóng gói PrixAuto.exe (PyInstaller cần một file script, không chạy được `-m rewards_bot`).

Bản .exe không có console: lỗi không bắt được thì ghi traceback ra data/crash.log cạnh PrixAuto.exe và báo đường dẫn.
"""
import sys
import time
import traceback
from pathlib import Path


def _crash(exc: BaseException) -> None:
    log = Path(sys.executable).resolve().parent / "data" / "crash.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"===== {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("".join(traceback.format_exception(exc)))
    except OSError:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"PrixAuto gặp lỗi và phải đóng.\nChi tiết: {log}", "PrixAuto", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from rewards_bot.__main__ import main
        main()
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001 (ghi mọi lỗi trước khi app tắt)
        _crash(e)
        sys.exit(1)
