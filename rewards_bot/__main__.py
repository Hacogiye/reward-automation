"""
PrixAuto

    python -m rewards_bot                        # mở giao diện
    python -m rewards_bot --run-all [--headless] # chạy tất cả tài khoản không cần giao diện
    python -m rewards_bot --check                # kiểm tra (chẩn đoán) tất cả tài khoản, không search
"""

import argparse
import os
import sys

from . import APP_NAME
from .core.instance import AlreadyRunning, single_instance


def _safe_console() -> None:
    """In tiếng Việt ra console Windows (cp1252) không làm app chết. Bản .exe không có console: PyInstaller để stdout là
    None hoặc một luồng giả mã cp1252 không đổi được, nên thay bằng luồng rỗng UTF-8."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def main() -> None:
    _safe_console()
    ap = argparse.ArgumentParser(prog="rewards_bot")
    ap.add_argument("--run-all", action="store_true", help="chạy tất cả tài khoản không mở giao diện")
    ap.add_argument("--check", action="store_true", help="kiểm tra tất cả tài khoản (không search)")
    ap.add_argument("--headless", action="store_true", help="chạy ẩn trình duyệt")
    args = ap.parse_args()
    try:
        with single_instance():
            if args.run_all or args.check:
                from .cli import run_cli
                run_cli(args.headless, action="check" if args.check else "run")
                return
            try:
                from .ui.webapp import main as web_main
            except ImportError as e:
                print(f"Thiếu thư viện giao diện ({e}). Cài bằng: pip install -r requirements.txt")
                sys.exit(1)
            web_main()
    except AlreadyRunning:
        msg = f"{APP_NAME} đang chạy ở cửa sổ khác. Đóng cửa sổ đó trước khi mở lại."
        print(msg)
        if not (args.run_all or args.check):  # chỉ hiện hộp thoại khi mở giao diện, không chặn lệnh chạy tự động
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, msg, APP_NAME, 0x40)
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
