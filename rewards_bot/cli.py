"""Chạy tất cả tài khoản không mở giao diện (dùng cho Task Scheduler), hoặc chỉ kiểm tra (--check)."""

import random
import threading
import time

from .core import security
from .core.config import DATA_DIR, HISTORY_FILE, load_settings
from .core.runner import Runner
from .search.bank import QueryBank


def start_jitter(max_minutes=None, sleep=time.sleep, rnd=random) -> float:
    """Lịch tự chạy: chờ ngẫu nhiên 0..max_minutes phút trước khi bắt đầu, để ngày nào cũng không chạy đúng một giờ.

    Gọi trước khi giữ khóa chạy 1 bản, nên trong lúc chờ vẫn mở được giao diện. Trả số giây đã chờ."""
    if max_minutes is None:
        max_minutes = load_settings().get("start_jitter_max", 30)
    try:
        max_minutes = max(0, min(120, int(max_minutes)))
    except (TypeError, ValueError):
        return 0.0
    if not max_minutes:
        return 0.0
    wait = rnd.uniform(0, max_minutes * 60)
    print(f"[{time.strftime('%H:%M:%S')}] Chờ ngẫu nhiên {wait / 60:.1f} phút trước khi chạy "
          f"(đổi trong Cài đặt, hoặc thêm --now để chạy ngay)", flush=True)
    sleep(wait)
    return wait


def run_cli(headless: bool, action: str = "run") -> None:
    security.harden_data_dir(DATA_DIR)
    settings = load_settings()
    if headless:
        settings["headless"] = True
    if not settings["profiles"]:
        print("Chưa có tài khoản nào. Mở giao diện (python -m rewards_bot) để thêm tài khoản.")
        return
    bank = QueryBank(HISTORY_FILE, int(settings.get("history_days", 30)))
    finished = threading.Event()
    left = {p["name"] for p in settings["profiles"]}
    lock = threading.Lock()

    def done(name):
        with lock:
            left.discard(name)
            if not left:
                finished.set()

    def status(name, data):
        for item in data.get("check") or []:  # kết quả --check
            mark = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}[item["level"]]
            print(f"  [{name}] {mark} {item['title']}: {item['detail']}", flush=True)

    runner = Runner(bank,
                    log=lambda n, m: print(f"[{time.strftime('%H:%M:%S')}] [{n}] {m}", flush=True),
                    status=status, done=done)
    runner.start(settings["profiles"], settings, action=action)
    try:
        while not finished.wait(1):
            pass
    except KeyboardInterrupt:
        runner.stop()
        runner.wait(30)
