import base64

import pytest

pytest.importorskip("webview")

from rewards_bot.core import config  # noqa: E402
from rewards_bot.ui import webapp as W  # noqa: E402


class FakeRunner:
    running = {}

    def is_running(self, name):
        return False

    def start(self, *a, **k):
        pass


@pytest.fixture
def api(data_dir, monkeypatch):
    monkeypatch.setattr(W, "POINTS_HISTORY_FILE", data_dir / "ph.json")
    monkeypatch.setattr(W, "DASHBOARD_FILE", data_dir / "dash.json")
    monkeypatch.setattr(W, "save_settings", lambda s: None)
    a = W.Api.__new__(W.Api)
    a._settings = {"profiles": []}
    a._pstate, a._history = {}, {}
    a._runner = FakeRunner()
    import threading
    a._lock = threading.Lock()
    return a


@pytest.mark.parametrize("key,value,ok", [
    ("max_parallel", 3, True), ("max_parallel", 99, False), ("headless", "yes", False),
    ("browser_channel", "evil", False), ("search_delay_min", True, False), ("bypass_proxy", False, True),
    ("fun_mode", True, True), ("fun_mode", False, True), ("fun_mode", "yes", False), ("fun_mode", 1, False),
    ("stall_after", 6, True), ("stall_after", 2, False), ("stall_after", 31, False),
    ("visual_max_tries", 1, True), ("visual_max_tries", 0, False), ("visual_max_tries", 11, False),
    ("log_keep_days", 90, True), ("log_keep_days", 0, False), ("log_keep_days", "14", False),
    ("fun_mode", None, False),
    ("onboarded", True, True), ("onboarded", "1", False),
    ("risk_ack", "1.3.0", True), ("risk_ack", "", True), ("risk_ack", "yes", False), ("risk_ack", 1, False),
    ("risk_ack", "1.3.0<script>", False), ("risk_ack", "1" * 20, False),
])
def test_setting_validation(key, value, ok):
    if ok:
        assert W._clean_setting(key, value) == value
    else:
        with pytest.raises(ValueError):
            W._clean_setting(key, value)


@pytest.mark.parametrize("profile", [
    {"name": "..\\..\\Windows"}, {"name": "x" * 50}, {"name": "ok", "mode": "evil"},
    {"name": "ok", "mode": "cdp", "cdp_port": 22}, {"name": ""},
])
def test_bad_profiles_rejected(api, profile):
    assert api.save_profile(None, profile)["ok"] is False


def test_new_profile_gets_dir_and_rename_keeps_it(api):
    assert api.save_profile(None, {"name": "nam anh"})["ok"]
    p = api._settings["profiles"][0]
    assert p["dir"] == "nam anh"
    api._history["nam anh"] = {"2026-10-20": {"available": 1}}
    api._pstate["nam anh"] = {"points": 1}
    assert api.save_profile("nam anh", {"name": "Nam Anh chính"})["ok"]
    assert p["name"] == "Nam Anh chính" and p["dir"] == "nam anh"
    assert "Nam Anh chính" in api._history and "nam anh" not in api._history
    assert "Nam Anh chính" in api._pstate


def test_unknown_action_rejected(api):
    assert W.Api.start(api, None, "rm -rf")["ok"] is False
    assert "check" in W.ACTIONS


@pytest.mark.skipif(not W.credentials.supported(), reason="DPAPI chỉ có trên Windows")
def test_credentials_follow_profile_and_never_leak(api):
    assert api.save_profile(None, {"name": "a"})["ok"]
    assert api.save_credentials("nope", "x@y.z", "pw")["ok"] is False
    r = api.save_credentials("a", "me@example.com", "pw-123")
    assert r["ok"] and r["credentials"]["emails"] == {"a": "me@example.com"}
    assert "pw-123" not in repr(api._cred_info())  # giao diện không bao giờ nhận lại mật khẩu
    assert api.save_profile("a", {"name": "b"})["ok"]  # đổi tên tài khoản: mật khẩu đi theo
    assert W.credentials.load("b") == ("me@example.com", "pw-123")
    api.delete_profiles(["b"])  # xóa tài khoản: xóa luôn mật khẩu
    assert W.credentials.emails() == {}


def test_history_records_missing_tasks(api):
    tasks = [{"group": "Tìm kiếm", "title": "Search PC", "progress": 90, "max": 90, "done": True},
             {"group": "Hoạt động", "title": "Edge – Minutes", "progress": 0, "max": 30, "done": False},
             {"group": "Task thêm", "title": "Browse", "progress": 5, "max": 30, "done": False}]
    api._events = W.queue.Queue()
    api._on_status("a", {"stats": {"available": 10, "today": 5}, "tasks": tasks})
    day = next(iter(api._history["a"].values()))
    assert day["today"] == 5 and day["missing"] == [{"t": "Edge – Minutes", "g": "Hoạt động", "p": 0, "m": 30}]


def test_goal_validation_and_follows_profile(api):
    assert api.save_profile(None, {"name": "a"})["ok"]
    assert api.set_goal("nope", "x", 100)["ok"] is False
    for bad in (-5, 1.5, "100", True, 10**9):
        assert api.set_goal("a", "Thẻ quà", bad)["ok"] is False
    assert api.set_goal("a", "x" * 61, 100)["ok"] is False
    r = api.set_goal("a", "  Thẻ quà 5$ ", 6500)
    assert r["ok"] and r["goals"] == {"a": {"title": "Thẻ quà 5$", "points": 6500}}
    assert api.save_profile("a", {"name": "b"})["ok"]  # đổi tên tài khoản: mục tiêu đi theo
    assert "b" in api._settings["goals"] and "a" not in api._settings["goals"]
    assert api.set_goal("b", "", 0)["goals"] == {}  # 0 điểm = xóa mục tiêu
    api.set_goal("b", "", 100)
    api.delete_profiles(["b"])
    assert api._settings["goals"] == {}


def test_app_info_has_name(api):
    info = api._app_info()
    assert info["name"] == "PrixAuto" and info["version"] == W.__version__
    assert W.SETTING_SCHEMA["check_updates"] == (bool,)


def test_check_update_reports_tag_and_install_only_for_exe(api, monkeypatch):
    from rewards_bot.core import updater
    asset = {"name": "PrixAuto-9.0.0-win64.zip", "size": 1, "api_url": "https://api.github.com/a/2", "sha256_url": "x"}
    info = {"current": W.__version__, "latest": "9.0.0", "tag": "v9.0.0", "newer": True,
            "url": updater.RELEASES_URL + "/tag/v9.0.0", "changes": [{"version": "9.0.0", "notes": "n"}], "asset": asset}
    monkeypatch.setattr(updater, "check", lambda cur: dict(info))
    monkeypatch.setattr(W.config, "FROZEN", False)
    r = api.check_update()
    assert r["ok"] and r["newer"] and r["latest"] == "9.0.0" and r["changes"] == info["changes"]
    assert "asset" not in r and r["ready"] and not r["can_install"]  # bản mã nguồn: chỉ báo, không tự cài
    assert not api.download_update()["ok"]
    monkeypatch.setattr(W.config, "FROZEN", True)
    monkeypatch.setattr(W.sys, "platform", "win32")
    assert api.check_update()["can_install"]

    def boom(cur):
        raise updater.UpdateError("Không kết nối được GitHub (x)")
    monkeypatch.setattr(updater, "check", boom)
    assert api.check_update() == {"ok": False, "error": "Không kết nối được GitHub (x)", "current": W.__version__}


def test_download_update_needs_built_release(api, monkeypatch):
    from rewards_bot.core import updater
    monkeypatch.setattr(W.config, "FROZEN", True)
    monkeypatch.setattr(updater, "check", lambda cur: {"current": "1", "latest": "9.0.0", "tag": "v9.0.0", "newer": True,
                                                       "url": updater.RELEASES_URL, "changes": [], "asset": None})
    assert not api.check_update()["ready"]
    r = api.download_update()
    assert not r["ok"] and "chuẩn bị" in r["error"]
    assert not api.apply_update()["ok"]  # chưa tải thì không cài


def test_open_releases_only_opens_this_repo(api, monkeypatch):
    import webbrowser
    from rewards_bot.core import updater
    opened = []
    monkeypatch.setattr(webbrowser, "open", opened.append)
    api._release = {"url": "https://evil.example.com/x"}
    api.open_releases()
    api._release = {"url": updater.RELEASES_URL + "/tag/v9.0.0"}
    api.open_releases()
    assert opened == [updater.RELEASES_URL, updater.RELEASES_URL + "/tag/v9.0.0"]


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_open_log_folder_fixed_path(api, monkeypatch, tmp_path, platform):
    """TC-8.3: mở đúng data/logs; Windows dùng os.startfile, nơi khác dùng xdg-open. Không nhận đường dẫn từ giao diện."""
    calls = []
    monkeypatch.setattr(W.config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(W.sys, "platform", platform)
    monkeypatch.setattr(W.os, "startfile", lambda p: calls.append(("startfile", p)), raising=False)
    monkeypatch.setattr(W.subprocess, "Popen", lambda args, **k: calls.append(("popen", args)))
    assert api.open_log_folder()["ok"]
    assert (tmp_path / "logs").is_dir()
    if platform == "win32":
        assert calls == [("startfile", tmp_path / "logs")]
    else:
        assert calls == [("popen", ["xdg-open", str(tmp_path / "logs")])]
    import inspect
    assert list(inspect.signature(W.Api.open_log_folder).parameters) == ["self"]


def test_avatar_validated_and_follows_profile(api):
    import base64
    assert api.save_profile(None, {"name": "a"})["ok"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    url = "data:image/png;base64," + base64.b64encode(png).decode()
    r = api.set_avatar("a", url)
    assert r["ok"] and r["avatars"]["a"] == url
    assert api.set_avatar("a", "data:image/svg+xml;base64,PHN2Zz4=")["ok"] is False  # SVG có thể chứa script
    assert api.set_avatar("a", "data:image/png;base64," + base64.b64encode(b"GIF89a").decode())["ok"] is False
    assert api.set_avatar("a", "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 400_000).decode())["ok"] is False
    assert api.set_avatar("nope", url)["ok"] is False
    assert api.set_avatar("a", url)["ok"]
    assert api.save_profile("a", {"name": "b"})["ok"]  # ảnh theo thư mục profile: đổi tên vẫn còn
    assert api._avatars() == {"b": url}
    assert api.set_avatar("b", None)["avatars"] == {}
    api.set_avatar("b", url)
    api.delete_profiles(["b"])
    assert not any(W.config.AVATAR_DIR.glob("*"))


@pytest.mark.parametrize("replacement", [
    "data:image/svg+xml;base64,PHN2Zz4=",
    "data:image/png;base64,!",
    "data:image/png;base64,R0lGODlh",
    "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 400_000).decode(),
])
def test_rejected_avatar_keeps_previous_image(api, replacement):
    import base64
    api.save_profile(None, {"name": "a"})
    original = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\noriginal").decode()
    assert api.set_avatar("a", original)["ok"]
    assert not api.set_avatar("a", replacement)["ok"]
    assert api._avatars() == {"a": original}


def test_avatar_replace_failure_preserves_previous_image(api, monkeypatch):
    import base64
    api.save_profile(None, {"name": "a"})
    original = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\noriginal").decode()
    assert api.set_avatar("a", original)["ok"]

    def denied(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(W.os, "replace", denied)
    replacement = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xffnew").decode()
    result = api.set_avatar("a", replacement)
    assert result["ok"] is False and result["error"]
    assert api._avatars() == {"a": original}
    assert [f.suffix for f in W.config.AVATAR_DIR.iterdir()] == [".png"]


def test_everything_turns_on_all_tasks_without_saving(api):
    seen = {}
    api._runner.start = lambda profs, settings, action: seen.update(settings=settings, action=action)
    api._settings.update({"do_browse": False, "do_pc": False, "do_quest_tasks": False})
    assert api.save_profile(None, {"name": "a"})["ok"]
    assert api.start(None, "everything")["ok"]
    assert seen["action"] == "run" and all(seen["settings"][k] for k in W.EVERYTHING)
    assert api._settings["do_browse"] is False  # cài đặt đã lưu không đổi


def test_app_icon_is_real_ico_on_windows(monkeypatch):
    # WinForms của pywebview chỉ nhận .ico: đưa PNG vào là app crash ngay khi mở (lỗi run.bat 2026-11)
    monkeypatch.setattr(W.sys, "platform", "win32")
    ico = W.app_icon()
    assert ico.suffix == ".ico" and ico.read_bytes()[:4] == b"\x00\x00\x01\x00"
    monkeypatch.setattr(W.sys, "platform", "linux")
    png = W.app_icon()
    assert png.suffix == ".png" and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_save_profile_proxy(api):
    assert api.save_profile(None, {"name": "a", "proxy": "1.2.3.4:8080"})["ok"]
    assert api._find("a")["proxy"] == "http://1.2.3.4:8080"
    r = api.save_profile("a", {"name": "a", "proxy": "http://u:p@1.2.3.4:8080"})
    assert r["ok"] is False and "mật khẩu" in r["error"]
    assert api.save_profile("a", {"name": "a", "proxy": ""})["ok"]
    assert api._find("a")["proxy"] == ""
    assert api.save_profile("a", {"name": "a", "mode": "cdp", "proxy": "1.2.3.4:80"})["ok"]
    assert api._find("a")["proxy"] == ""  # gắn vào Edge đang mở: proxy do Edge đó tự đặt


def test_fun_mode_default_off_and_saved(api):
    """TC-2.4: fun_mode mặc định tắt, có trong SETTING_SCHEMA; save_settings kiểm tra kiểu bool như các công tắc khác."""
    assert config.DEFAULT_SETTINGS["fun_mode"] is False
    assert "fun_mode" in W.SETTING_SCHEMA and W.SETTING_SCHEMA["fun_mode"] == (bool,)
    api._settings.update(config.DEFAULT_SETTINGS)
    api._bank = type("B", (), {"history_days": 0})()
    assert api.save_settings({"fun_mode": "yes"})["ok"] is False
    assert api._settings["fun_mode"] is False
    r = api.save_settings({"fun_mode": True})
    assert r["ok"] and r["settings"]["fun_mode"] is True and api._settings["fun_mode"] is True


def test_window_background_follows_fun_mode():
    """Cyberpunk đã lưu mà tắt chế độ vui: nền cửa sổ là nền tối thường, không phải nền neon."""
    assert W._window_background("cyberpunk", True) == "#0b1022"
    assert W._window_background("cyberpunk", False) == "#151f2c"

def test_linux_csp_relaxed_only_in_served_copy():
    original = (W.WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert "'unsafe-eval'" not in original  # bản gốc (Windows) giữ CSP chặt
    linux = W._linux_index_html()
    assert "script-src 'self' 'unsafe-eval';" in linux
    assert linux.replace(" 'unsafe-eval'", "", 1) == original


def test_pump_sends_ascii_only_script(api):
    import queue
    import threading
    import time
    sent = []
    api._events = queue.Queue()
    api._window = type("Win", (), {"evaluate_js": lambda self, s: sent.append(s)})()
    api._events.put({"type": "log", "name": "a", "msg": "Đang làm mới – xong"})
    threading.Thread(target=api._pump, daemon=True).start()
    deadline = time.time() + 3
    while not sent and time.time() < deadline:
        time.sleep(0.05)
    assert sent and sent[0].isascii()  # GTK cắt cụt script có ký tự nhiều byte
    assert "\\u0110ang l\\u00e0m m\\u1edbi" in sent[0]
