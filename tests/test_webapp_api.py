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


def test_update_check_and_token(api, monkeypatch):
    monkeypatch.setattr(W.updater, "latest_release", lambda token: {
        "tag": "v9.0.0", "version": "9.0.0", "name": "v9", "notes": "", "url": "", "asset": {"name": "x", "size": 1, "api_url": ""}})
    r = api.check_update()
    assert r["ok"] and r["newer"] and r["latest"] == "9.0.0"
    assert r["can_install"] is False  # chạy từ mã nguồn: không tự cài, dùng git pull
    assert api.download_update()["ok"] is False
    assert api.set_update_token("not-a-token")["ok"] is False
    if W.credentials.supported():
        tok = "github_pat_" + "A" * 40
        assert api.set_update_token(tok)["app"]["has_token"] is True
        assert tok not in repr(api._app_info())
        assert api.set_update_token("")["app"]["has_token"] is False


def test_update_check_error_is_reported(api, monkeypatch):
    def boom(token):
        raise W.updater.UpdateError("Không kết nối được GitHub")
    monkeypatch.setattr(W.updater, "latest_release", boom)
    assert api.check_update() == {"ok": False, "error": "Không kết nối được GitHub", "current": W.__version__}


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
