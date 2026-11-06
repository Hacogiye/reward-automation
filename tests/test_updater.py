"""Cập nhật: so phiên bản, đọc bản phát hành, kiểm tra zip và SHA-256, script cài không đụng data/."""
import hashlib
import io
import json
import urllib.error
import zipfile

import pytest

from rewards_bot.core import updater as U


def test_versions():
    assert U.parse_version("v1.2.0") == (1, 2, 0) and U.parse_version("1.3") == (1, 3, 0)
    assert U.parse_version("latest") is None
    assert U.is_newer("v1.10.0", "1.9.9") and not U.is_newer("v1.2.0", "1.2.0") and not U.is_newer("junk", "1.0")


class Resp(io.BytesIO):
    def __init__(self, body: bytes, headers=None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_latest_release_picks_win64_zip():
    body = {"tag_name": "v1.3.0", "name": "Bản 1.3", "body": "Sửa lỗi", "html_url": "https://github.com/x/releases/v1.3.0",
            "assets": [{"name": "notes.txt", "url": "https://api.github.com/a/1"},
                       {"name": "RewardsBot-1.3.0-win64.zip", "size": 1234, "url": "https://api.github.com/a/2"},
                       {"name": "RewardsBot-1.3.0-win64.zip.sha256", "size": 90, "url": "https://api.github.com/a/3"}]}
    seen = {}

    def opener(req, timeout):
        seen["auth"] = req.get_header("Authorization")
        return Resp(json.dumps(body).encode())

    r = U.latest_release(opener=opener)
    assert r["version"] == "1.3.0" and r["asset"] == {"name": "RewardsBot-1.3.0-win64.zip", "size": 1234,
                                                       "api_url": "https://api.github.com/a/2",
                                                       "sha256_url": "https://api.github.com/a/3"}
    assert seen["auth"] is None  # repo công khai: không gửi token


def test_no_release_yet_explains():
    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    with pytest.raises(U.UpdateError, match="Chưa có bản phát hành"):
        U.latest_release(opener=opener)


def make_zip(path, names):
    with zipfile.ZipFile(path, "w") as z:
        for n in names:
            z.writestr(n, "x")
    return path


def test_verify_zip(tmp_path):
    U.verify_zip(make_zip(tmp_path / "ok.zip", ["RewardsBot/RewardsBot.exe", "RewardsBot/_internal/a.dll"]))
    for i, names in enumerate((["RewardsBot/_internal/a.dll"], ["RewardsBot/RewardsBot.exe", "RewardsBot/../../evil.exe"],
                               ["RewardsBot/RewardsBot.exe", "Other/x.exe"], ["RewardsBot/RewardsBot.exe", "/abs.exe"],
                               ["RewardsBot/RewardsBot.exe", "RewardsBot/data/settings.json"])):
        with pytest.raises(U.UpdateError):
            U.verify_zip(make_zip(tmp_path / f"bad{i}.zip", names))
    (tmp_path / "junk.zip").write_bytes(b"not a zip")
    with pytest.raises(U.UpdateError, match="hỏng"):
        U.verify_zip(tmp_path / "junk.zip")


def test_apply_script_keeps_data_and_restarts(tmp_path):
    inst = tmp_path / "App's folder"
    s = U.apply_script(tmp_path / "u.zip", inst, 4321, tmp_path / "work")
    assert "Wait-Process -Id 4321" in s and "/XD" in s and str(tmp_path / "work" / "staging" / "RewardsBot" / "data") in s
    assert "App''s folder" in s  # nháy đơn trong đường dẫn được escape
    assert s.strip().splitlines()[-1].startswith("Start-Process") and "RewardsBot.exe" in s.splitlines()[-1]


def fake_github(monkeypatch, zip_bytes: bytes, sha_text: str, location="https://objects.githubusercontent.com/f?sig=1"):
    """api.github.com trả 302 sang máy chủ file; a/2 = zip, a/3 = file .sha256."""
    files = {"https://api.github.com/a/2": zip_bytes, "https://api.github.com/a/3": sha_text.encode()}
    sent = []

    class Opener:
        def open(self, req, timeout):
            sent.append(req.full_url)
            raise urllib.error.HTTPError(req.full_url, 302, "Found", {"Location": location + "&f=" + req.full_url}, None)

    def urlopen(req, timeout):
        body = files[req.full_url.split("&f=", 1)[1]]
        return Resp(body, {"Content-Length": str(len(body))})

    monkeypatch.setattr(U.urllib.request, "build_opener", lambda *h: Opener())
    monkeypatch.setattr(U.urllib.request, "urlopen", urlopen)
    return sent


def zip_bytes() -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr("RewardsBot/RewardsBot.exe", "x")
    return data.getvalue()


ASSET = {"name": "RewardsBot-1.3.0-win64.zip", "size": 10, "api_url": "https://api.github.com/a/2",
         "sha256_url": "https://api.github.com/a/3"}


def test_download_checks_sha256(tmp_path, monkeypatch):
    body = zip_bytes()
    fake_github(monkeypatch, body, hashlib.sha256(body).hexdigest() + "  RewardsBot-1.3.0-win64.zip\n")
    assert U.download(ASSET, tmp_path / "u.zip").read_bytes() == body


@pytest.mark.parametrize("sha, match", [("0" * 64 + "  x.zip", "SHA-256"), ("not a hash", "không đúng dạng")])
def test_download_rejects_bad_sha256(tmp_path, monkeypatch, sha, match):
    fake_github(monkeypatch, zip_bytes(), sha)
    with pytest.raises(U.UpdateError, match=match):
        U.download(ASSET, tmp_path / "u.zip")
    assert not (tmp_path / "u.zip").exists() and not (tmp_path / "u.part").exists()


def test_download_requires_sha256_file(tmp_path):
    with pytest.raises(U.UpdateError, match=".sha256"):
        U.download({**ASSET, "sha256_url": ""}, tmp_path / "u.zip")


def test_download_refuses_foreign_redirect(tmp_path, monkeypatch):
    body = zip_bytes()
    fake_github(monkeypatch, body, hashlib.sha256(body).hexdigest(), location="https://evil.example.com/f?x=1")
    with pytest.raises(U.UpdateError, match="địa chỉ lạ"):
        U.download(ASSET, tmp_path / "u.zip")


def test_download_refuses_foreign_hosts(tmp_path):
    with pytest.raises(U.UpdateError):
        U.download({"api_url": "https://evil.example.com/a.zip", "size": 1,
                    "sha256_url": "https://evil.example.com/a.sha256"}, tmp_path / "u.zip")
