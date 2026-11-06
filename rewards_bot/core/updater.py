"""Kiểm tra và cài bản mới từ GitHub Releases cho bản đóng gói RewardsBot.exe.

Bản phát hành là file zip `RewardsBot-<phiên bản>-win64.zip` chứa thư mục `RewardsBot/` (RewardsBot.exe + _internal/),
kèm file `<tên zip>.sha256`. Cài đặt: tải zip về data/update/, so SHA-256 và kiểm tra nội dung, rồi một script
PowerShell chạy sau khi app đóng sẽ chép đè file mới lên thư mục cài đặt (KHÔNG đụng data/: phiên đăng nhập, cài đặt,
mật khẩu đã mã hóa) và mở lại app. Repo công khai nên không cần token.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from .. import __version__

REPO = "NT101-lc/reward-automation"
RELEASES_URL = f"https://github.com/{REPO}/releases"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_RE = re.compile(r"^RewardsBot-[\w.]+-win64\.zip$")
EXE_NAME = "RewardsBot.exe"
APP_FOLDER = "RewardsBot"
MAX_ASSET_BYTES = 400 * 1024 * 1024
# chỉ tải từ GitHub (API trả về link chuyển tiếp sang máy chủ file của GitHub)
_ALLOWED_HOSTS = ("api.github.com", "github.com", "objects.githubusercontent.com",
                  "release-assets.githubusercontent.com", "github-releases.githubusercontent.com")


class UpdateError(RuntimeError):
    pass


def parse_version(text):
    """"v1.2.0" / "1.2" -> (1, 2, 0); không hợp lệ -> None."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(text or "").strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def is_newer(latest, current=__version__) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def _headers(accept="application/vnd.github+json") -> dict:
    return {"Accept": accept, "User-Agent": f"RewardsBot/{__version__}", "X-GitHub-Api-Version": "2022-11-28"}


def _allowed(url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname or "") in _ALLOWED_HOSTS


def latest_release(timeout: float = 15, opener=urllib.request.urlopen) -> dict:
    """Thông tin bản phát hành mới nhất: {version, tag, name, notes, url, asset{name,size,api_url,sha256_url}}."""
    req = urllib.request.Request(LATEST_API, headers=_headers())
    try:
        with opener(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("Chưa có bản phát hành nào trên GitHub") from None
        raise UpdateError(f"GitHub trả lỗi {e.code}") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(f"Không kết nối được GitHub ({getattr(e, 'reason', e)})") from None
    tag = str(data.get("tag_name") or "")
    assets = data.get("assets") or []
    asset = next((a for a in assets if ASSET_RE.match(str(a.get("name") or ""))), None)
    sha = asset and next((a for a in assets if a.get("name") == asset["name"] + ".sha256"), None)
    return {
        "version": ".".join(map(str, parse_version(tag))) if parse_version(tag) else tag,
        "tag": tag,
        "name": str(data.get("name") or tag)[:120],
        "notes": str(data.get("body") or "")[:3000],
        "url": str(data.get("html_url") or RELEASES_URL),
        "asset": {"name": asset["name"], "size": int(asset.get("size") or 0), "api_url": asset["url"],
                  "sha256_url": sha["url"] if sha else ""} if asset else None,
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _open(url: str, timeout: float):
    """Mở file của bản phát hành; GitHub chuyển tiếp sang link có chữ ký, chỉ đi theo nếu vẫn là host của GitHub."""
    if not _allowed(url):
        raise UpdateError("Link tải không phải của GitHub")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        return opener.open(urllib.request.Request(url, headers=_headers("application/octet-stream")), timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise UpdateError(f"Tải bản cập nhật lỗi {e.code}") from None
        location = e.headers.get("Location", "")
        if not _allowed(location):
            raise UpdateError("GitHub chuyển tới địa chỉ lạ, dừng tải") from None
        try:
            return urllib.request.urlopen(
                urllib.request.Request(location, headers={"User-Agent": f"RewardsBot/{__version__}"}), timeout=timeout)
        except (urllib.error.URLError, OSError) as e2:
            raise UpdateError(f"Không tải được bản cập nhật ({getattr(e2, 'reason', e2)})") from None
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError(f"Không tải được bản cập nhật ({getattr(e, 'reason', e)})") from None


def _expected_sha256(asset: dict, timeout: float) -> str:
    """Đọc mã SHA-256 trong file `<zip>.sha256` (dạng `sha256sum`: "<64 ký tự hex>  <tên file>")."""
    if not asset.get("sha256_url"):
        raise UpdateError("Bản phát hành thiếu file .sha256, không cài để an toàn")
    with _open(asset["sha256_url"], timeout) as r:
        text = r.read(4096).decode("ascii", "replace")
    m = re.match(r"\s*([0-9a-fA-F]{64})(?![0-9a-fA-F])", text)
    if not m:
        raise UpdateError("File .sha256 của bản phát hành không đúng dạng")
    return m.group(1).lower()


def download(asset: dict, dest: Path, progress=None, timeout: float = 60) -> Path:
    """Tải file zip của bản phát hành về dest, so SHA-256 với file .sha256 đi kèm rồi kiểm tra nội dung zip."""
    if asset.get("size", 0) > MAX_ASSET_BYTES:
        raise UpdateError("File cập nhật quá lớn")
    expected = _expected_sha256(asset, timeout)
    resp = _open(asset["api_url"], timeout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    total, done, h = int(resp.headers.get("Content-Length") or asset.get("size") or 0), 0, hashlib.sha256()
    with resp, open(tmp, "wb") as f:
        while chunk := resp.read(1024 * 256):
            done += len(chunk)
            if done > MAX_ASSET_BYTES:
                raise UpdateError("File cập nhật quá lớn")
            h.update(chunk)
            f.write(chunk)
            if progress:
                progress(done, total)
    if h.hexdigest() != expected:
        tmp.unlink(missing_ok=True)
        raise UpdateError("File cập nhật không khớp mã SHA-256, đã xóa (tải lại sau)")
    os.replace(tmp, dest)
    verify_zip(dest)
    return dest


def verify_zip(path: Path) -> None:
    """Zip phải chứa RewardsBot/RewardsBot.exe, không có đường dẫn tuyệt đối / '..' (chống ghi ra ngoài thư mục)."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            bad = z.testzip()
    except zipfile.BadZipFile:
        raise UpdateError("File cập nhật bị hỏng (không phải zip)") from None
    if bad:
        raise UpdateError(f"File cập nhật bị hỏng ({bad})")
    for n in names:
        parts = n.replace("\\", "/").split("/")
        if n.startswith(("/", "\\")) or ":" in parts[0] or ".." in parts or parts[0] != APP_FOLDER:
            raise UpdateError(f"File cập nhật có đường dẫn không hợp lệ: {n}")
        if len(parts) > 1 and parts[1].lower() == "data":  # bản cập nhật không bao giờ được đụng tới data/
            raise UpdateError(f"File cập nhật chứa thư mục data/: {n}")
    if f"{APP_FOLDER}/{EXE_NAME}" not in names:
        raise UpdateError(f"File cập nhật không có {EXE_NAME}")


def apply_script(zip_path: Path, install_dir: Path, pid: int, work: Path) -> str:
    """Script PowerShell: đợi app đóng, giải nén, chép đè (bỏ qua data/), mở lại app, ghi update.log."""
    def q(p) -> str:  # chuỗi PowerShell trong nháy đơn
        return "'" + str(p).replace("'", "''") + "'"

    staging, log = work / "staging", work / "update.log"
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$log = {q(log)}",
        "function Log($m) { Add-Content -LiteralPath $log -Value ((Get-Date -Format s) + ' ' + $m) -Encoding UTF8 }",
        "try {",
        f"  Wait-Process -Id {int(pid)} -Timeout 90 -ErrorAction SilentlyContinue",
        "  Start-Sleep -Seconds 1",
        f"  if (Test-Path -LiteralPath {q(staging)}) {{ Remove-Item -LiteralPath {q(staging)} -Recurse -Force }}",
        f"  Expand-Archive -LiteralPath {q(zip_path)} -DestinationPath {q(staging)} -Force",
        # robocopy: chép đè, giữ nguyên data/ (phiên đăng nhập, cài đặt); mã thoát < 8 là thành công
        # /XD so khớp thư mục NGUỒN: loại data/ của bản giải nén (verify_zip cũng đã chặn)
        f"  robocopy {q(staging / APP_FOLDER)} {q(install_dir)} /E /XD {q(staging / APP_FOLDER / 'data')} "
        "/R:3 /W:2 /NFL /NDL /NJH /NJS | Out-Null",
        "  if ($LASTEXITCODE -ge 8) { throw \"robocopy lỗi $LASTEXITCODE\" }",
        "  Log 'Đã cập nhật xong'",
        "} catch { Log ('Lỗi cập nhật: ' + $_) }",
        f"Start-Process -FilePath {q(install_dir / EXE_NAME)} -WorkingDirectory {q(install_dir)}",
    ])


def start_apply(zip_path: Path, install_dir: Path, work: Path) -> None:
    """Chạy script cập nhật ở tiến trình riêng (tách khỏi app) rồi app tự thoát để file không bị khóa."""
    if sys.platform != "win32":
        raise UpdateError("Tự cập nhật chỉ có trên bản Windows (.exe)")
    verify_zip(zip_path)
    script = work / "apply.ps1"
    script.write_text(apply_script(zip_path, install_dir, os.getpid(), work), encoding="utf-8-sig")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                     creationflags=flags, close_fds=True)
