import json
import os

import pytest

from rewards_bot.core import edge_launcher as el


def test_args_have_no_automation_flags():
    exe = os.path.join("Edge", "msedge.exe")  # basename phải ra msedge.exe trên mọi OS
    args = el.build_args(exe, os.path.join("data", "profiles", "a"), headless=False, extra=["--no-proxy-server"])
    joined = " ".join(args)
    for bad in ("--enable-automation", "--disable-background-networking", "--disable-sync", "--disable-extensions",
                "--disable-gpu", "--headless"):
        assert bad not in joined
    assert el.BOT_MARKER in args  # để nhận ra Edge mồ côi của bot
    assert "--remote-debugging-address=127.0.0.1" in args  # cổng debug chỉ nghe trên máy này
    assert "--disable-blink-features=AutomationControlled" in args
    assert "--edge-skip-compat-layer-relaunch" in args
    assert "--no-proxy-server" in args
    assert args[-1] == "about:blank"


def test_headless_hides_window_without_disabling_gpu():
    args = el.build_args("chrome.exe", "d", headless=True)
    assert "--headless=new" in args and "--window-position=-32000,-32000" in args
    assert "--disable-gpu" not in args and "--edge-skip-compat-layer-relaunch" not in args


def test_read_port(tmp_path):
    assert el.read_port(str(tmp_path)) is None
    (tmp_path / "DevToolsActivePort").write_text("51234\n/devtools/browser/abc\n", encoding="utf-8")
    assert el.read_port(str(tmp_path)) == 51234
    (tmp_path / "DevToolsActivePort").write_text("", encoding="utf-8")
    assert el.read_port(str(tmp_path)) is None


def test_headless_uses_normal_user_agent(tmp_path):
    exe = tmp_path / "msedge.exe"
    exe.write_text("")
    (tmp_path / "155.0.4283.62").mkdir()
    (tmp_path / "154.0.1.2").mkdir()
    args = el.build_args(str(exe), "d", headless=True)
    ua = next(a for a in args if a.startswith("--user-agent="))
    assert "Headless" not in ua and "Chrome/155.0.0.0" in ua and ua.endswith("Edg/155.0.0.0")
    assert not any(a.startswith("--user-agent=") for a in el.build_args(str(exe), "d", headless=False))


def test_find_browser_on_linux(monkeypatch):
    monkeypatch.setattr(el.sys, "platform", "linux")
    paths = {"microsoft-edge-stable": "/usr/bin/microsoft-edge-stable", "chromium": "/usr/bin/chromium"}
    monkeypatch.setattr(el.shutil, "which", lambda name: paths.get(name))
    monkeypatch.setattr(el.os.path, "exists", lambda p: False)
    assert el.find_browser("msedge") == "/usr/bin/microsoft-edge-stable"
    assert el.find_browser("chrome") == "/usr/bin/chromium"
    monkeypatch.setattr(el.shutil, "which", lambda name: None)
    import pytest
    with pytest.raises(el.LaunchError):
        el.find_browser("msedge")


def test_version_and_user_agent_on_linux(monkeypatch):
    assert el.parse_version_output("Microsoft Edge 155.0.4283.62 \n") == "155"
    assert el.parse_version_output("Chromium 141.0.7390.54 built on Debian") == "141"
    assert el.parse_version_output("") is None
    monkeypatch.setattr(el.sys, "platform", "linux")
    monkeypatch.setattr(el, "browser_version", lambda exe: "155")
    ua = el.normal_user_agent("/usr/bin/microsoft-edge-stable")
    assert "X11; Linux x86_64" in ua and ua.endswith("Edg/155.0.0.0") and "Headless" not in ua
    assert "Edg/" not in el.normal_user_agent("/usr/bin/google-chrome")
    args = el.build_args("/usr/bin/microsoft-edge-stable", "/d", headless=True)
    assert "--edge-skip-compat-layer-relaunch" not in args  # cờ này chỉ dành cho Edge trên Windows


def _local_state(d, last_used, **profiles):
    info = {k: {"user_name": v} for k, v in profiles.items()}
    (d / "Local State").write_text(json.dumps({"profile": {"last_used": last_used, "info_cache": info}}), encoding="utf-8")


def test_pinned_profile_keeps_first_choice(tmp_path):
    # thư mục mới chưa có gì: ghim Default
    assert el.pinned_profile(str(tmp_path / "new")) == "Default"
    _local_state(tmp_path, "Profile 1", **{"Default": "work@company.com", "Profile 1": "me@gmail.com"})
    assert el.pinned_profile(str(tmp_path)) == "Profile 1"  # lần đầu: profile dùng gần nhất
    _local_state(tmp_path, "Default", **{"Default": "work@company.com", "Profile 1": "me@gmail.com"})
    assert el.pinned_profile(str(tmp_path)) == "Profile 1"  # đã ghim: Edge đổi last_used cũng không đổi theo
    assert el.edge_profiles(str(tmp_path)) == {"Default": "work@company.com", "Profile 1": "me@gmail.com"}


def test_repin_to_last_used_after_user_switches_profile(tmp_path):
    # tài khoản mới: bot ghim Default; trong cửa sổ đăng nhập người dùng chuyển sang Profile 2
    assert el.pinned_profile(str(tmp_path)) == "Default"
    (tmp_path / "Profile 2").mkdir()
    _local_state(tmp_path, "Profile 2", **{"Default": "", "Profile 2": "me@gmail.com"})
    assert el.repin_to_last_used(str(tmp_path)) == ("Default", "Profile 2")
    assert el.pinned_profile(str(tmp_path)) == "Profile 2"
    assert el.repin_to_last_used(str(tmp_path)) is None  # không đổi gì thì giữ nguyên
    _local_state(tmp_path, "Profile 9", **{"Profile 2": "me@gmail.com"})  # thư mục profile không có: bỏ qua
    assert el.repin_to_last_used(str(tmp_path)) is None and el.pinned_profile(str(tmp_path)) == "Profile 2"


def test_signed_in_profiles_ignores_display_names(tmp_path):
    info = {"Default": {"name": "Profile 1"}, "Profile 2": {"user_name": "me@gmail.com", "name": "Me"}}
    (tmp_path / "Local State").write_text(json.dumps({"profile": {"info_cache": info}}), encoding="utf-8")
    assert el.signed_in_profiles(str(tmp_path)) == {"Profile 2": "me@gmail.com"}
    assert el.edge_profiles(str(tmp_path)) == {"Default": "Profile 1", "Profile 2": "me@gmail.com"}


def test_pinned_profile_rejects_bad_names(tmp_path):
    (tmp_path / el.PIN_FILE).write_text("../../evil", encoding="utf-8")
    assert el.pinned_profile(str(tmp_path)) == "Default"
    args = el.build_args("msedge.exe", "d", headless=False, profile_directory="Profile 1")
    assert "--profile-directory=Profile 1" in args
    with pytest.raises(ValueError):
        el.build_args("msedge.exe", "d", headless=False, profile_directory="--remote-debugging-port=9")
