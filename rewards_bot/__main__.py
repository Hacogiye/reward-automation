"""
PrixAuto

    python -m rewards_bot                        # mở giao diện
    python -m rewards_bot --run-all [--headless] # chạy tất cả tài khoản không cần giao diện
    python -m rewards_bot --check                # kiểm tra (chẩn đoán) tất cả tài khoản, không search
    python -m rewards_bot --checkin              # chỉ check-in app điện thoại cho tất cả tài khoản (giữ chuỗi)
    (--run-all / --checkin chờ ngẫu nhiên 0..start_jitter_max phút trước khi chạy; thêm --now để chạy ngay)
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
    ap.add_argument("--checkin", action="store_true",
                    help="chỉ check-in app điện thoại cho tất cả tài khoản (lịch riêng để giữ chuỗi)")
    ap.add_argument("--headless", action="store_true", help="chạy ẩn trình duyệt")
    ap.add_argument("--now", action="store_true",
                    help="--run-all / --checkin chạy ngay, không chờ ngẫu nhiên trước khi bắt đầu")
    args = ap.parse_args()
    if (args.run_all or args.checkin) and not args.now:
        from .cli import start_jitter
        try:
            start_jitter()
        except KeyboardInterrupt:
            return
    try:
        with single_instance():
            if args.run_all or args.check or args.checkin:
                from .cli import run_cli
                run_cli(args.headless, action="check" if args.check else "checkin" if args.checkin else "run")
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
        if not (args.run_all or args.check or args.checkin):  # chỉ hiện hộp thoại khi mở giao diện, không chặn lệnh chạy tự động
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, msg, APP_NAME, 0x40)
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
