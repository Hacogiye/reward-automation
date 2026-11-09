"""Giao diện web (pywebview + Edge WebView2). Python giữ toàn bộ logic, JS chỉ hiển thị.

JS gọi Python qua window.pywebview.api.<hàm>(); Python đẩy sự kiện (log, trạng thái)
sang JS theo lô mỗi 250ms qua window.onEvents([...]).
"""

import base64
import json
import queue
import sys
import threading
import time
from pathlib import Path

import webview

from .. import __version__
from ..core import credentials, security, updater
from ..core import config
from ..core.config import (DATA_DIR, DASHBOARD_FILE, HISTORY_FILE, POINTS_HISTORY_FILE, load_settings, new_profile_dir,
                           read_json, save_settings, write_json)
from ..core.runner import Runner
from ..search.bank import QueryBank

WEB_DIR = Path(__file__).resolve().parent / "web"
# Kiểu và khoảng hợp lệ của từng cài đặt: mọi giá trị từ giao diện đều được kiểm tra trước khi lưu
SETTING_SCHEMA = {
    "search_delay_min": (int, 1, 600), "search_delay_max": (int, 1, 600), "extra_searches": (int, 0, 20),
    "max_parallel": (int, 1, 10), "history_days": (int, 0, 365),
    "browse_minutes": (int, 1, 240),
    "search_browse": (bool,), "search_click_pct": (int, 0, 100),
    "stall_after": (int, 3, 30), "visual_max_tries": (int, 1, 10), "log_keep_days": (int, 1, 90),
    "headless": (bool,), "do_quests": (bool,), "do_pc": (bool,), "do_mobile": (bool,), "do_visual": (bool,),
    "do_browse": (bool,), "bypass_proxy": (bool,), "check_updates": (bool,), "fun_mode": (bool,),
    "browse_auto_stop": (bool,), "do_quest_tasks": (bool,), "custom_searches": (bool,),
    "pc_searches": (int, 0, 50), "mobile_searches": (int, 0, 50),
    "browser_channel": (str, ("msedge", "chrome", "")),
    "theme": (str, ("system", "light", "dark", "cyberpunk")),
    "language": (str, ("vi", "en")),
}
SETTING_KEYS = tuple(SETTING_SCHEMA)
ACTIONS = {"run", "refresh", "login", "check", "everything"}
# "Làm tất cả": chạy như "run" nhưng bật mọi việc, bỏ qua các công tắc (không đổi cài đặt đã lưu)
EVERYTHING = {"do_quests": True, "do_quest_tasks": True, "do_visual": True, "do_pc": True, "do_mobile": True,
              "do_browse": True}
AVATAR_MAX_BYTES = 300 * 1024
# ảnh đại diện: chỉ nhận PNG / JPEG / WebP (kiểm tra cả byte đầu file, không tin phần khai báo)
AVATAR_TYPES = {"image/png": (b"\x89PNG\r\n\x1a\n", "png"), "image/jpeg": (b"\xff\xd8\xff", "jpg"),
                "image/webp": (b"RIFF", "webp")}
NAME_MAX = 40
GOAL_TITLE_MAX = 60
GOAL_POINTS_MAX = 10_000_000
BAD_NAME_CHARS = set('\\/:*?"<>|')  # ký tự không hợp lệ trong tên thư mục Windows


def _clean_setting(key, value):
    """Trả về giá trị đã kiểm tra, hoặc raise ValueError."""
    kind, *rule = SETTING_SCHEMA[key]
    if kind is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} phải là bật/tắt")
        return value
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise ValueError(f"{key} phải là số nguyên")
        lo, hi = rule
        if not lo <= value <= hi:
            raise ValueError(f"{key} phải trong khoảng {lo}-{hi}")
        return int(value)
    if value not in rule[0]:
        raise ValueError(f"{key} không hợp lệ")
    return value


def _missing(tasks: list) -> list:
    """Các task chưa xong: [{"t": tiêu đề, "g": nhóm, "p": đã làm, "m": cần}] (Daily Set, Keep earning, hoạt động...)."""
    out = []
    for r in tasks:
        if not isinstance(r, dict) or r.get("done") or r.get("group") == "Task thêm":
            continue
        out.append({"t": str(r.get("title", ""))[:80], "g": r.get("group", ""), "p": r.get("progress"), "m": r.get("max")})
    return out


def _save(path: Path, data) -> None:
    try:
        write_json(path, data)
    except OSError:
        pass


class Api:
    """Các hàm JS gọi được. Tên hàm không bắt đầu bằng '_' mới được lộ ra JS."""

    def __init__(self):
        self._window = None
        self._settings = load_settings()
        self._events: queue.Queue = queue.Queue()
        # câu search vẫn sinh tự động (đa lĩnh vực, không trùng) dù không còn trang bảng search
        self._bank = QueryBank(HISTORY_FILE, int(self._settings.get("history_days", 30)))
        try:  # repo đã công khai: xóa token GitHub cũ (từng cần khi repo riêng tư) nếu còn lưu
            credentials.remove_secret("github_token")
        except OSError:
            pass
        self._runner = Runner(
            self._bank,
            log=lambda n, m: self._events.put({"type": "log", "name": n, "msg": m, "time": time.strftime("%H:%M:%S")}),
            status=self._on_status,
            done=lambda n: self._events.put({"type": "done", "name": n}),
        )
        cache = read_json(DASHBOARD_FILE, {})
        self._pstate = {n: {"state": "Sẵn sàng", "progress": "", **d} for n, d in cache.items()}
        self._history = read_json(POINTS_HISTORY_FILE, {})
        self._lock = threading.Lock()
        for w in config.LOAD_WARNINGS:  # file dữ liệu hỏng -> báo trong nhật ký thay vì âm thầm bỏ qua
            self._events.put({"type": "log", "name": "app", "msg": "cảnh báo: " + w, "time": time.strftime("%H:%M:%S")})

    # ------------------------------------------------------------ nội bộ
    def _on_status(self, name: str, data: dict) -> None:
        with self._lock:
            st = self._pstate.setdefault(name, {"state": "Sẵn sàng", "progress": ""})
            st.update(data)
            if data.get("stats") and data["stats"].get("available") is not None:
                day = {**data["stats"]}
                if isinstance(data.get("tasks"), list):  # việc còn thiếu trong ngày, cho trang Lịch sử
                    day["missing"] = _missing(data["tasks"])
                self._history.setdefault(name, {})[time.strftime("%Y-%m-%d")] = day
                _save(POINTS_HISTORY_FILE, self._history)
            if any(k in data for k in ("tasks", "points", "stats", "check")):
                keep = ("points", "today", "tasks", "stats", "icons", "streak", "updated", "check", "check_time")
                _save(DASHBOARD_FILE, {n: {k: s.get(k) for k in keep if k in s} for n, s in self._pstate.items()})
        self._events.put({"type": "status", "name": name, "data": data,
                          "history": self._history.get(name) if "stats" in data else None})

    def _pump(self) -> None:
        """Gửi sự kiện sang JS theo lô."""
        while True:
            batch = [self._events.get()]
            time.sleep(0.25)
            while not self._events.empty() and len(batch) < 500:
                batch.append(self._events.get_nowait())
            if self._window:
                try:
                    self._window.evaluate_js(f"window.onEvents && window.onEvents({json.dumps(batch, ensure_ascii=False)})")
                except Exception:
                    pass

    def _profiles(self) -> list:
        return self._settings["profiles"]

    def _find(self, name):
        return next((p for p in self._profiles() if p["name"] == name), None)

    # ------------------------------------------------------------ gọi từ JS
    def bootstrap(self) -> dict:
        with self._lock:
            return {
                "settings": {k: self._settings.get(k) for k in SETTING_KEYS},
                "profiles": self._profiles(),
                "pstate": self._pstate,
                "history": self._history,
                "running": list(self._runner.running),
                "credentials": self._cred_info(),
                "goals": self._settings.get("goals", {}),
                "avatars": self._avatars(),
                "app": self._app_info(),
            }

    # ------------------------------------------------------------ ảnh đại diện
    def _avatar_files(self, p: dict) -> list:
        d = config.AVATAR_DIR
        return [d / f"{p['dir']}.{ext}" for _, ext in AVATAR_TYPES.values()] if p.get("dir") else []

    def _avatars(self) -> dict:
        """{tên tài khoản: data URL} để hiện ảnh (theo thư mục profile nên đổi tên tài khoản không mất ảnh)."""
        out = {}
        for p in self._profiles():
            for f in self._avatar_files(p):
                if f.exists():
                    mime = next(m for m, (_, ext) in AVATAR_TYPES.items() if f.suffix == "." + ext)
                    out[p["name"]] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode("ascii")
                    break
        return out

    def set_avatar(self, name, data_url) -> dict:
        """Lưu ảnh đại diện (data URL đã được giao diện cắt vuông, thu nhỏ); data_url rỗng = xóa ảnh."""
        p = self._find(name) if isinstance(name, str) else None
        if not p or not p.get("dir"):
            return {"ok": False, "error": "Không có tài khoản này."}
        for f in self._avatar_files(p):
            f.unlink(missing_ok=True)
        if data_url:
            head, _, b64 = str(data_url).partition(",")
            mime = head.removeprefix("data:").removesuffix(";base64")
            if not head.startswith("data:") or not head.endswith(";base64") or mime not in AVATAR_TYPES:
                return {"ok": False, "error": "Chỉ nhận ảnh PNG, JPEG hoặc WebP."}
            try:
                raw = base64.b64decode(b64, validate=True)
            except ValueError:
                return {"ok": False, "error": "Ảnh bị hỏng."}
            magic, ext = AVATAR_TYPES[mime]
            if len(raw) > AVATAR_MAX_BYTES or not raw.startswith(magic):
                return {"ok": False, "error": "Ảnh quá lớn hoặc không đúng định dạng."}
            config.AVATAR_DIR.mkdir(parents=True, exist_ok=True)
            (config.AVATAR_DIR / f"{p['dir']}.{ext}").write_bytes(raw)
        return {"ok": True, "avatars": self._avatars()}

    # ------------------------------------------------------------ cập nhật
    def _app_info(self) -> dict:
        return {"version": __version__, "frozen": config.FROZEN, "releases": updater.RELEASES_URL}

    def check_update(self) -> dict:
        """Hỏi GitHub bản mới nhất. Không có bản mới / lỗi mạng thì không làm phiền người dùng."""
        try:
            rel = updater.latest_release()
        except updater.UpdateError as e:
            return {"ok": False, "error": str(e), "current": __version__}
        self._release = rel
        newer = updater.is_newer(rel["tag"])
        return {"ok": True, "current": __version__, "latest": rel["version"], "newer": newer, "notes": rel["notes"],
                "name": rel["name"], "can_install": newer and config.FROZEN and bool(rel["asset"])}

    def open_releases(self) -> dict:
        """Mở trang bản phát hành trên GitHub bằng trình duyệt mặc định (chỉ đúng địa chỉ của repo này)."""
        import webbrowser
        webbrowser.open(updater.RELEASES_URL)
        return {"ok": True}

    def download_update(self) -> dict:
        rel = getattr(self, "_release", None)
        if not config.FROZEN:
            return {"ok": False, "error": "Đang chạy từ mã nguồn: cập nhật bằng git pull."}
        if not rel or not rel.get("asset") or not updater.is_newer(rel["tag"]):
            return {"ok": False, "error": "Không có bản mới để tải."}
        if getattr(self, "_downloading", False):
            return {"ok": True}
        self._downloading = True

        def work():
            dest = config.UPDATE_DIR / rel["asset"]["name"]
            last = [0.0]

            def progress(done, total):
                if time.time() - last[0] > 0.5:
                    last[0] = time.time()
                    self._events.put({"type": "update", "state": "downloading", "done": done, "total": total})
            try:
                updater.download(rel["asset"], dest, progress)
                self._update_zip = dest
                self._events.put({"type": "update", "state": "ready", "version": rel["version"]})
            except (updater.UpdateError, OSError) as e:
                self._events.put({"type": "update", "state": "error", "error": str(e)})
            finally:
                self._downloading = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def apply_update(self) -> dict:
        """Chạy script cài (đợi app đóng rồi chép đè, giữ data/) và đóng app."""
        z = getattr(self, "_update_zip", None)
        if not z:
            return {"ok": False, "error": "Chưa tải bản cập nhật."}
        if self._runner.running:
            return {"ok": False, "error": "Dừng các tài khoản đang chạy trước khi cập nhật."}
        try:
            updater.start_apply(z, config.BASE_DIR, config.UPDATE_DIR)
        except (updater.UpdateError, OSError) as e:
            return {"ok": False, "error": str(e)}
        threading.Timer(0.8, lambda: [w.destroy() for w in list(webview.windows)]).start()
        return {"ok": True}

    def set_goal(self, name, title, points) -> dict:
        """Đặt mục tiêu đổi quà cho 1 tài khoản; points = 0/None thì xóa mục tiêu."""
        if not isinstance(name, str) or not self._find(name):
            return {"ok": False, "error": "Không có tài khoản này."}
        goals = self._settings.setdefault("goals", {})
        if not points:
            goals.pop(name, None)
        else:
            title = str(title or "").strip() or "Mục tiêu"
            if isinstance(points, bool) or not isinstance(points, (int, float)) or int(points) != points                     or not 1 <= points <= GOAL_POINTS_MAX:
                return {"ok": False, "error": f"Số điểm phải là số nguyên từ 1 đến {GOAL_POINTS_MAX:,}."}
            if len(title) > GOAL_TITLE_MAX or not title.isprintable():
                return {"ok": False, "error": f"Tên mục tiêu tối đa {GOAL_TITLE_MAX} ký tự."}
            goals[name] = {"title": title, "points": int(points)}
        save_settings(self._settings)
        return {"ok": True, "goals": goals}

    @staticmethod
    def _cred_info() -> dict:
        """Chỉ cho giao diện biết tài khoản nào đã lưu mật khẩu (kèm email), không bao giờ gửi mật khẩu."""
        return {"supported": credentials.supported(), "emails": credentials.emails()}

    def save_credentials(self, name, email, password) -> dict:
        if not isinstance(name, str) or not self._find(name):
            return {"ok": False, "error": "Không có tài khoản này."}
        if not credentials.supported():
            return {"ok": False, "error": "Chỉ lưu được mật khẩu trên Windows (mã hóa DPAPI)."}
        try:
            credentials.save(name, str(email or ""), str(password or ""))
        except (ValueError, OSError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "credentials": self._cred_info()}

    def delete_credentials(self, name) -> dict:
        if isinstance(name, str):
            credentials.remove(name)
        return {"ok": True, "credentials": self._cred_info()}

    def save_profile(self, old_name, profile: dict) -> dict:
        if not isinstance(profile, dict):
            return {"ok": False, "error": "Dữ liệu không hợp lệ."}
        name = str(profile.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Nhập tên profile."}
        if len(name) > NAME_MAX or BAD_NAME_CHARS & set(name) or not name.isprintable():
            return {"ok": False, "error": f'Tên tối đa {NAME_MAX} ký tự, không chứa các ký tự {" ".join(sorted(BAD_NAME_CHARS))}'}
        mode = profile.get("mode", "managed")
        if mode not in ("managed", "cdp"):
            return {"ok": False, "error": "Chế độ không hợp lệ."}
        try:
            port = security.validate_port(profile.get("cdp_port") or 9222)
            proxy = security.validate_proxy(profile.get("proxy")) if mode == "managed" else ""
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if name != old_name and self._find(name):
            return {"ok": False, "error": "Đã có profile tên này."}
        if old_name and self._runner.is_running(old_name):
            return {"ok": False, "error": "Dừng profile trước khi sửa."}
        p = {"name": name, "mode": mode, "cdp_port": port, "proxy": proxy}
        old = self._find(old_name) if old_name else None
        with self._lock:
            if old:
                old.update(p)  # giữ nguyên old["dir"]: đổi tên không làm mất phiên đăng nhập
                if old_name != name:
                    for store in (self._pstate, self._history):
                        if old_name in store:
                            store[name] = store.pop(old_name)
                    _save(POINTS_HISTORY_FILE, self._history)
                    credentials.rename(old_name, name)
                    goals = self._settings.get("goals", {})
                    if old_name in goals:
                        goals[name] = goals.pop(old_name)
            else:
                p["dir"] = new_profile_dir(name, taken=[x.get("dir") for x in self._profiles()])
                self._profiles().append(p)
            save_settings(self._settings)
        return {"ok": True, "profiles": self._profiles()}

    def delete_profiles(self, names: list) -> dict:
        names = [n for n in (names or []) if isinstance(n, str) and not self._runner.is_running(n)]
        for p in self._profiles():
            if p["name"] in names:
                for f in self._avatar_files(p):
                    f.unlink(missing_ok=True)
        self._settings["profiles"] = [p for p in self._profiles() if p["name"] not in names]
        for n in names:
            self._settings.get("goals", {}).pop(n, None)
        save_settings(self._settings)
        for n in names:  # xóa tài khoản thì xóa luôn mật khẩu đã lưu
            credentials.remove(n)
        return {"ok": True, "profiles": self._profiles()}

    def start(self, names, action: str = "run") -> dict:
        if action not in ACTIONS:
            return {"ok": False, "error": "Lệnh không hợp lệ", "running": list(self._runner.running)}
        profs = self._profiles() if not names else [p for p in map(self._find, names) if p]
        settings = dict(self._settings)
        if action == "everything":
            settings.update(EVERYTHING)
            action = "run"
        self._runner.start(profs, settings, action=action)
        return {"ok": True, "running": list(self._runner.running)}

    def stop(self, names=None) -> dict:
        self._runner.stop(names or None)
        return {"ok": True}

    def save_settings(self, partial: dict) -> dict:
        try:
            clean = {k: _clean_setting(k, v) for k, v in (partial or {}).items() if k in SETTING_SCHEMA}
        except ValueError as e:
            return {"ok": False, "error": str(e), "settings": {k: self._settings.get(k) for k in SETTING_KEYS}}
        self._settings.update(clean)
        if self._settings["search_delay_max"] < self._settings["search_delay_min"]:
            self._settings["search_delay_max"] = self._settings["search_delay_min"]
        self._bank.history_days = int(self._settings["history_days"])
        save_settings(self._settings)
        return {"ok": True, "settings": {k: self._settings.get(k) for k in SETTING_KEYS}}


def _windows_dark() -> bool:
    """Windows đang dùng giao diện tối cho ứng dụng?"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except (OSError, ImportError):  # ImportError: không phải Windows (không có winreg)
        return False


def app_icon() -> Path:
    """Icon cửa sổ app: .ico trên Windows (WinForms không đọc được PNG), PNG ở nơi khác."""
    return WEB_DIR / "assets" / ("app-icon.ico" if sys.platform == "win32" else "app-icon-256.png")


def _window_background(theme: str, fun_mode: bool = True) -> str:
    """Màu nền cửa sổ khi trang chưa vẽ xong, khớp sáng/tối để không bị nháy."""
    if theme == "cyberpunk" and not fun_mode:  # chế độ vui tắt: Cyberpunk hiển thị như giao diện tối
        theme = "dark"
    if theme == "cyberpunk":
        return "#0b1022"
    dark = theme == "dark" or (theme == "system" and _windows_dark())
    return "#151f2c" if dark else "#f6f8fb"


def main() -> None:
    security.harden_data_dir(DATA_DIR)
    api = Api()
    window = webview.create_window("Microsoft Rewards Bot", url=str(WEB_DIR / "index.html"), js_api=api,
                                   width=1320, height=880, min_size=(1020, 680),
                                   background_color=_window_background(api._settings.get("theme", "system"),
                                                                     bool(api._settings.get("fun_mode"))),
                                   text_select=True)  # cho bôi đen / copy nhật ký
    api._window = window

    def on_closing():
        # dừng bot và đợi trình duyệt đóng hẳn, tránh để Edge chạy ngầm giữ profile
        api._runner.stop()
        api._runner.wait(15)

    window.events.closing += on_closing
    threading.Thread(target=api._pump, daemon=True).start()
    # http_server: pywebview phục vụ thư mục web/ qua 127.0.0.1 (cổng ngẫu nhiên) để CSP 'self' áp dụng được;
    # trang mở bằng file:// thì Chromium không coi là 'self' và chặn luôn app.js
    # Windows: Edge WebView2. Linux/macOS: để pywebview tự chọn (GTK/WebKitGTK, Qt hoặc Cocoa)
    # icon cửa sổ: WinForms (Windows) chỉ nhận .ico, đưa PNG vào là crash ngay khi mở; GTK/Qt dùng PNG
    webview.start(gui="edgechromium" if sys.platform == "win32" else None, debug=False, http_server=True,
                  icon=str(app_icon()))
