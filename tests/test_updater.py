"""Cập nhật: phát hiện bản mới theo tag, danh sách thay đổi, kiểm tra zip và SHA-256, script cài không đụng data/,
ghi chú release sinh từ commit."""
import hashlib
import io
import json
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

from rewards_bot.core import updater as U

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))
import release_notes as RN  # noqa: E402


def test_versions():
    assert U.parse_version("v1.2.0") == (1, 2, 0) and U.parse_version("1.3") == (1, 3, 0)
    assert U.parse_version("latest") is None and U.parse_version("v1.3.0-beta") is None
    assert U.is_newer("v1.10.0", "1.9.9") and not U.is_newer("v1.2.0", "1.2.0") and not U.is_newer("junk", "1.0")


class Resp(io.BytesIO):
    def __init__(self, body: bytes, headers=None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


TAGS = [{"name": "v1.4.0"}, {"name": "v1.6.0"}, {"name": "v1.5.0"}, {"name": "v2.0.0-beta"}, {"name": "nightly"}]
RELEASES = [
    {"tag_name": "v1.6.0", "name": "PrixAuto v1.6.0", "body": "Bản 1.6", "published_at": "2026-11-20T10:00:00Z",
     "html_url": "https://github.com/NT101-lc/reward-automation/releases/tag/v1.6.0",
     "assets": [{"name": "notes.txt", "url": "https://api.github.com/a/1"},
                {"name": "PrixAuto-1.6.0-win64.zip", "size": 1234, "url": "https://api.github.com/a/2"},
                {"name": "PrixAuto-1.6.0-win64.zip.sha256", "size": 90, "url": "https://api.github.com/a/3"}]},
    {"tag_name": "v2.0.0-beta", "prerelease": True, "body": "beta", "assets": []},
    {"tag_name": "v1.5.0", "name": "PrixAuto v1.5.0", "body": "Bản 1.5", "published_at": "2026-11-12T10:00:00Z", "assets": []},
    {"tag_name": "v1.4.0", "body": "Bản 1.4", "assets": []},
]


def github(tags=TAGS, releases=RELEASES):
    seen = []

    def opener(req, timeout):
        seen.append((req.full_url, req.get_header("Authorization")))
        if "/tags" in req.full_url:
            return Resp(json.dumps(tags).encode())
        if "/releases" in req.full_url:
            return Resp(json.dumps(releases).encode())
        raise AssertionError(req.full_url)
    return opener, seen


def test_check_uses_tags_and_lists_changes_of_every_newer_release():
    opener, seen = github()
    r = U.check("1.4.0", opener=opener)
    assert r["newer"] and r["latest"] == "1.6.0" and r["tag"] == "v1.6.0"
    # mới nhất trước; bỏ bản đang dùng, bản cũ hơn và prerelease
    assert [c["version"] for c in r["changes"]] == ["1.6.0", "1.5.0"]
    assert r["changes"][0]["notes"] == "Bản 1.6" and r["changes"][0]["date"] == "2026-11-20"
    assert r["asset"] == {"name": "PrixAuto-1.6.0-win64.zip", "size": 1234, "api_url": "https://api.github.com/a/2",
                          "sha256_url": "https://api.github.com/a/3"}
    assert r["url"].endswith("/releases/tag/v1.6.0")
    assert all(auth is None for _, auth in seen)  # repo công khai: không gửi token


def test_up_to_date_asks_only_for_tags():
    opener, seen = github()
    r = U.check("1.6.0", opener=opener)
    assert not r["newer"] and r["changes"] == [] and r["asset"] is None
    assert len(seen) == 1 and "/tags" in seen[0][0]


def test_tag_without_release_yet_is_still_reported():
    """Tag vừa đẩy, workflow chưa build xong: vẫn báo bản mới nhưng chưa có file để cài."""
    opener, _ = github(releases=RELEASES[2:])
    r = U.check("1.5.0", opener=opener)
    assert r["newer"] and r["latest"] == "1.6.0" and r["asset"] is None and r["changes"] == []


def test_network_errors_explain():
    def rate_limited(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    def offline(req, timeout):
        raise urllib.error.URLError("no network")
    with pytest.raises(U.UpdateError, match="giới hạn"):
        U.check("1.0.0", opener=rate_limited)
    with pytest.raises(U.UpdateError, match="Không kết nối"):
        U.check("1.0.0", opener=offline)


def make_zip(path, names):
    with zipfile.ZipFile(path, "w") as z:
        for n in names:
            z.writestr(n, "x")
    return path


def test_verify_zip(tmp_path):
    U.verify_zip(make_zip(tmp_path / "ok.zip", ["PrixAuto/PrixAuto.exe", "PrixAuto/_internal/a.dll"]))
    for i, names in enumerate((["PrixAuto/_internal/a.dll"], ["PrixAuto/PrixAuto.exe", "PrixAuto/../../evil.exe"],
                               ["PrixAuto/PrixAuto.exe", "Other/x.exe"], ["PrixAuto/PrixAuto.exe", "/abs.exe"],
                               ["PrixAuto/PrixAuto.exe", "PrixAuto/data/settings.json"])):
        with pytest.raises(U.UpdateError):
            U.verify_zip(make_zip(tmp_path / f"bad{i}.zip", names))
    (tmp_path / "junk.zip").write_bytes(b"not a zip")
    with pytest.raises(U.UpdateError, match="hỏng"):
        U.verify_zip(tmp_path / "junk.zip")


def test_apply_script_keeps_data_and_restarts(tmp_path):
    inst = tmp_path / "App's folder"
    s = U.apply_script(tmp_path / "u.zip", inst, 4321, tmp_path / "work")
    assert "Wait-Process -Id 4321" in s and "/XD" in s and str(tmp_path / "work" / "staging" / "PrixAuto" / "data") in s
    assert "App''s folder" in s  # nháy đơn trong đường dẫn được escape
    assert s.strip().splitlines()[-1].startswith("Start-Process") and "PrixAuto.exe" in s.splitlines()[-1]


def fake_files(monkeypatch, zip_bytes: bytes, sha_text: str, location="https://objects.githubusercontent.com/f?sig=1"):
    """api.github.com trả 302 sang máy chủ file; a/2 = zip, a/3 = file .sha256."""
    files = {"https://api.github.com/a/2": zip_bytes, "https://api.github.com/a/3": sha_text.encode()}

    class Opener:
        def open(self, req, timeout):
            raise urllib.error.HTTPError(req.full_url, 302, "Found", {"Location": location + "&f=" + req.full_url}, None)

    def urlopen(req, timeout):
        body = files[req.full_url.split("&f=", 1)[1]]
        return Resp(body, {"Content-Length": str(len(body))})

    monkeypatch.setattr(U.urllib.request, "build_opener", lambda *h: Opener())
    monkeypatch.setattr(U.urllib.request, "urlopen", urlopen)


def good_zip() -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr("PrixAuto/PrixAuto.exe", "exe")
    return data.getvalue()


ASSET = {"name": "PrixAuto-1.6.0-win64.zip", "size": 0, "api_url": "https://api.github.com/a/2",
         "sha256_url": "https://api.github.com/a/3"}


def test_download_checks_sha256(tmp_path, monkeypatch):
    body = good_zip()
    fake_files(monkeypatch, body, hashlib.sha256(body).hexdigest() + "  PrixAuto-1.6.0-win64.zip\n")
    got = []
    dest = U.download(ASSET, tmp_path / "u" / "p.zip", progress=lambda d, t: got.append((d, t)))
    assert dest.read_bytes() == body and got[-1] == (len(body), len(body))

    fake_files(monkeypatch, body, "0" * 64 + "  x.zip\n")
    with pytest.raises(U.UpdateError, match="SHA-256"):
        U.download(ASSET, tmp_path / "u" / "bad.zip")
    assert not (tmp_path / "u" / "bad.zip").exists() and not (tmp_path / "u" / "bad.part").exists()


def test_download_refuses_foreign_redirect_and_missing_sha(tmp_path, monkeypatch):
    body = good_zip()
    fake_files(monkeypatch, body, hashlib.sha256(body).hexdigest(), location="https://evil.example.com/x?")
    with pytest.raises(U.UpdateError, match="địa chỉ lạ"):
        U.download(ASSET, tmp_path / "p.zip")
    with pytest.raises(U.UpdateError, match=".sha256"):
        U.download({**ASSET, "sha256_url": ""}, tmp_path / "p.zip")


CHANGELOG = """# Nhật ký thay đổi

Lời dẫn.

## 1.10.0 - 2026-12-01
- Thêm A
  dòng nối tiếp

## 1.9.0 - 2026-11-30

## 1.1.0 - 2026-11-01
- Bản cũ
"""


def test_release_notes_come_from_changelog():
    md = RN.build("v1.10.0", CHANGELOG, "v1.9.0")
    assert md == "- Thêm A\n  dòng nối tiếp\n\nSo sánh / Compare: v1.9.0...v1.10.0\n"
    assert RN.build("v1.1.0", CHANGELOG) == "- Bản cũ\n"
    for missing in ("v1.9.0", "v1.0.0", "v1.10"):  # mục rỗng, chưa viết, "1.10" không được khớp nhầm mục 1.10.0
        with pytest.raises(ValueError, match="CHANGELOG.md"):
            RN.build(missing, CHANGELOG)


def test_current_version_has_changelog_entry():
    """Bắt buộc: đổi __version__ thì phải viết mục tương ứng trong CHANGELOG.md, nếu không test đỏ ngay trên máy dev
    (và workflow phát hành dừng trước khi build)."""
    from rewards_bot import __version__
    text = RN.CHANGELOG.read_text(encoding="utf-8")
    assert RN.section(__version__, text), f"CHANGELOG.md chưa có mục '## {__version__} - <ngày>'"
    # mỗi tag đã phát hành từ khi có CHANGELOG đều phải còn mục của nó (không lỡ tay xóa)
    for v in ("1.7.0", "1.7.1", "1.7.2", "1.7.3"):
        assert RN.section(v, text), v


@pytest.mark.skipif(sys.platform != "win32", reason="chỉ Windows có PowerShell + robocopy")
def test_apply_script_really_runs_and_keeps_data(tmp_path):
    """Chạy script cài thật bằng đúng cách app khởi chạy nó (launch_script): file mới đè file cũ, data/ giữ nguyên.
    Bản 1.7.0 khởi chạy PowerShell với DETACHED_PROCESS nên script không bao giờ chạy."""
    inst = tmp_path / "App's folder"
    (inst / "_internal").mkdir(parents=True)
    (inst / "data").mkdir()
    (inst / U.EXE_NAME).write_text("old exe")
    (inst / "_internal" / "lib.txt").write_text("old lib")
    (inst / "data" / "settings.json").write_text("keep me")
    zp = tmp_path / "work" / "u.zip"
    zp.parent.mkdir()
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr(f"{U.APP_FOLDER}/{U.EXE_NAME}", "new exe")
        z.writestr(f"{U.APP_FOLDER}/_internal/lib.txt", "new lib")
        z.writestr(f"{U.APP_FOLDER}/_internal/added.txt", "added")
    script = tmp_path / "work" / "apply.ps1"
    # pid đã chết: Wait-Process trả về ngay; dòng Start-Process cuối sẽ lỗi vì exe giả, không sao
    script.write_text(U.apply_script(zp, inst, 999999, tmp_path / "work"), encoding="utf-8-sig")
    assert U.launch_script(script).wait(120) is not None
    assert (inst / U.EXE_NAME).read_text() == "new exe"
    assert (inst / "_internal" / "lib.txt").read_text() == "new lib" and (inst / "_internal" / "added.txt").exists()
    assert (inst / "data" / "settings.json").read_text() == "keep me"
    assert "Đã cập nhật xong" in (tmp_path / "work" / "update.log").read_text(encoding="utf-8-sig")
    assert not zp.exists() and not (tmp_path / "work" / "staging").exists()
