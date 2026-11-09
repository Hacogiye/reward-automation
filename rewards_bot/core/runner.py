"""Chạy nhiều profile song song, mỗi profile 1 thread + 1 trình duyệt riêng."""

import threading
import time
from datetime import date, timedelta

from .bot import RewardsBot
from .config import LOG_DIR
from ..search.bank import QueryBank

LOG_KEEP_DAYS = 14  # mặc định; chỉnh bằng cài đặt "log_keep_days"


class FileLog:
    """Ghi nhật ký ra data/logs/YYYY-MM-DD.log (giữ log_keep_days ngày) để xem lại sau khi tắt app."""

    def __init__(self, keep_days: int = LOG_KEEP_DAYS):
        self.lock = threading.Lock()
        self.prune(keep_days)

    @staticmethod
    def prune(keep_days: int) -> None:
        """Xóa file nhật ký cũ hơn keep_days ngày."""
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            cutoff = (date.today() - timedelta(days=max(1, int(keep_days)))).isoformat()
            for f in LOG_DIR.glob("*.log"):
                if f.stem < cutoff:
                    f.unlink()
        except (OSError, TypeError, ValueError):
            pass

    def write(self, name: str, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} [{name}] {msg}\n"
        with self.lock:
            try:
                with open(LOG_DIR / f"{date.today().isoformat()}.log", "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                pass


class Runner:
    """Chạy nhiều profile song song, mỗi profile 1 thread + 1 trình duyệt riêng."""

    def __init__(self, bank: QueryBank, log, status, done):
        self.bank = bank
        self._file_log = FileLog()

        def log_both(name, msg):
            self._file_log.write(name, msg)
            log(name, msg)

        self.log, self.status, self.done = log_both, status, done
        self.running: dict = {}  # name -> stop Event
        self.threads: dict = {}  # name -> Thread
        self.sem = None
        self.lock = threading.Lock()

    def is_running(self, name: str) -> bool:
        return name in self.running

    def start(self, profiles: list, settings: dict, action: str = "run") -> None:
        """action: "run" (làm task), "login" (mở cửa sổ đăng nhập), "refresh" (chỉ đọc điểm),
        "check" (tự chẩn đoán, không search)."""
        FileLog.prune(settings.get("log_keep_days", LOG_KEEP_DAYS))
        with self.lock:
            if not self.running or self.sem is None:
                self.sem = threading.Semaphore(max(1, int(settings.get("max_parallel", 3))))
            for prof in profiles:
                if prof["name"] in self.running:
                    continue
                ev = threading.Event()
                self.running[prof["name"]] = ev
                t = threading.Thread(target=self._worker, args=(dict(prof), dict(settings), ev, action), daemon=True)
                self.threads[prof["name"]] = t
                t.start()

    def _worker(self, prof, settings, ev, action) -> None:
        name = prof["name"]
        try:
            bot = RewardsBot(prof, settings, self.bank, self.log, self.status, ev)
            if action == "login":
                bot.login()
                return
            if action == "refresh":
                bot.refresh()
                return
            if action == "check":
                bot.diagnose()
                return
            self.status(name, {"state": "Đang chờ", "progress": "Chờ lượt chạy"})
            with self.sem:
                if not ev.is_set():
                    bot.run()
                else:
                    self.status(name, {"state": "Đã dừng", "progress": ""})
        except Exception as e:  # lỗi khởi tạo trình duyệt...
            self.status(name, {"state": "Lỗi", "progress": str(e)[:60]})
            self.log(name, f"Lỗi: {e}")
        finally:
            with self.lock:
                self.running.pop(name, None)
                self.threads.pop(name, None)
            self.done(name)

    def stop(self, names=None) -> None:
        with self.lock:
            for n, ev in self.running.items():
                if names is None or n in names:
                    ev.set()

    def wait(self, timeout: float) -> bool:
        """Đợi các thread kết thúc (để trình duyệt được đóng đàng hoàng). True nếu tất cả đã dừng."""
        deadline = time.time() + timeout
        for t in list(self.threads.values()):
            t.join(max(0.0, deadline - time.time()))
        return not any(t.is_alive() for t in self.threads.values())
