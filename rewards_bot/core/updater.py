"""Kiểm tra bản mới theo TAG phiên bản trên GitHub và cài bản mới cho PrixAuto.exe.

Chỉ nhìn tag dạng vX.Y.Z (không quan tâm commit / push lên nhánh): có tag mới hơn phiên bản đang chạy là có bản mới.
Danh sách thay đổi lấy từ phần ghi chú của các GitHub Release ứng với những tag mới hơn (workflow release.yml tạo).

Cài đặt (chỉ bản .exe trên Windows): release có file `PrixAuto-<phiên bản>-win64.zip` chứa thư mục `PrixAuto/`
(PrixAuto.exe + _internal/) kèm `<tên zip>.sha256`. Tải zip về data/update/, so SHA-256, kiểm tra nội dung, rồi một
script PowerShell chạy sau khi app đóng chép đè file mới lên thư mục cài đặt (KHÔNG đụng data/: phiên đăng nhập, cài đặt,
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

from .. import APP_NAME, __version__

REPO = "NT101-lc/reward-automation"
RELEASES_URL = f"https://github.com/{REPO}/releases"
TAGS_API = f"https://api.github.com/repos/{REPO}/tags?per_page=100"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
ASSET_RE = re.compile(rf"^{APP_NAME}-[\w.]+-win64\.zip$")
EXE_NAME = f"{APP_NAME}.exe"
APP_FOLDER = APP_NAME
MAX_ASSET_BYTES = 400 * 1024 * 1024
MAX_CHANGES = 10  # số bản phát hành tối đa hiện trong danh sách thay đổi
NOTES_MAX = 5000  # ký tự ghi chú tối đa mỗi bản
# chỉ tải từ GitHub (API trả về link chuyển tiếp sang máy chủ file của GitHub)
_ALLOWED_HOSTS = ("api.github.com", "github.com", "objects.githubusercontent.com",
                  "release-assets.githubusercontent.com", "github-releases.githubusercontent.com")


class UpdateError(RuntimeError):
    pass


def parse_version(text):
    """"v1.2.0" / "1.2" -> (1, 2, 0); tag khác (vd "v1.3.0-beta", "latest") -> None."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(text or "").strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def version_str(v) -> str:
    return ".".join(map(str, v))


def is_newer(latest, current=__version__) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def _headers(accept="application/vnd.github+json") -> dict:
    return {"Accept": accept, "User-Agent": f"{APP_NAME}/{__version__}", "X-GitHub-Api-Version": "2022-11-28"}


def _allowed(url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname or "") in _ALLOWED_HOSTS


def _get_json(url: str, timeout: float, opener):
    req = urllib.request.Request(url, headers=_headers())
    try:
        with opener(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise UpdateError("GitHub tạm giới hạn số lần hỏi, thử lại sau") from None
        raise UpdateError(f"GitHub trả lỗi {e.code}") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(f"Không kết nối được GitHub ({getattr(e, 'reason', e)})") from None


def latest_tag(timeout: float = 15, opener=urllib.request.urlopen):
    """Tag phiên bản cao nhất trên GitHub: (tên tag, (x, y, z)), hoặc None nếu chưa có tag nào."""
    data = _get_json(TAGS_API, timeout, opener)
    tags = [(str(t.get("name") or ""), parse_version(t.get("name"))) for t in data if isinstance(t, dict)]
    tags = [t for t in tags if t[1]]
    return max(tags, key=lambda t: t[1]) if tags else None


def _asset(rel: dict):
    assets = rel.get("assets") or []
    zip_ = next((a for a in assets if ASSET_RE.match(str(a.get("name") or ""))), None)
    if not zip_:
        return None
    sha = next((a for a in assets if a.get("name") == zip_["name"] + ".sha256"), None)
    return {"name": zip_["name"], "size": int(zip_.get("size") or 0), "api_url": str(zip_.get("url") or ""),
            "sha256_url": str(sha.get("url") or "") if sha else ""}


def check(current: str = __version__, timeout: float = 15, opener=urllib.request.urlopen) -> dict:
    """Hỏi GitHub có bản mới không (theo tag) và các thay đổi từ bản đang dùng tới bản mới nhất.

    Trả {"current", "latest", "tag", "newer", "url", "changes": [{version, tag, name, date, notes, url}], "asset"}.
    asset = None khi tag đã có nhưng bản cài (zip) chưa build xong.
    """
    cur = parse_version(current) or (0, 0, 0)
    top = latest_tag(timeout, opener)
    out = {"current": current, "latest": version_str(top[1]) if top else current, "tag": top[0] if top else "",
           "newer": bool(top and top[1] > cur), "url": RELEASES_URL, "changes": [], "asset": None}
    if not out["newer"]:
        return out
    releases = _get_json(RELEASES_API, timeout, opener)
    newer = []
    for r in releases if isinstance(releases, list) else []:
        v = parse_version(r.get("tag_name")) if isinstance(r, dict) else None
        if v and cur < v <= top[1] and not r.get("draft") and not r.get("prerelease"):
            newer.append((v, r))
    newer.sort(key=lambda x: x[0], reverse=True)
    for v, r in newer[:MAX_CHANGES]:
        out["changes"].append({
            "version": version_str(v), "tag": str(r.get("tag_name")), "name": str(r.get("name") or "")[:120],
            "date": str(r.get("published_at") or "")[:10], "notes": str(r.get("body") or "")[:NOTES_MAX],
            "url": str(r.get("html_url") or RELEASES_URL),
        })
    top_rel = next((r for v, r in newer if v == top[1]), None)
    if top_rel:
        out["asset"] = _asset(top_rel)
        if _allowed(str(top_rel.get("html_url") or "")):
            out["url"] = str(top_rel["html_url"])
    return out


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
                urllib.request.Request(location, headers={"User-Agent": f"{APP_NAME}/{__version__}"}), timeout=timeout)
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
    try:
        with resp, open(tmp, "wb") as f:
            while chunk := resp.read(1024 * 256):
                done += len(chunk)
                if done > MAX_ASSET_BYTES:
                    raise UpdateError("File cập nhật quá lớn")
                h.update(chunk)
                f.write(chunk)
                if progress:
                    progress(done, total)
    except (OSError, UpdateError) as e:
        tmp.unlink(missing_ok=True)
        if isinstance(e, UpdateError):
            raise
        raise UpdateError(f"Tải bản cập nhật bị ngắt ({e})") from None
    if h.hexdigest() != expected:
        tmp.unlink(missing_ok=True)
        raise UpdateError("File cập nhật không khớp mã SHA-256, đã xóa (tải lại sau)")
    os.replace(tmp, dest)
    verify_zip(dest)
    return dest


def verify_zip(path: Path) -> None:
    """Zip phải chứa PrixAuto/PrixAuto.exe, không có đường dẫn tuyệt đối / '..' (chống ghi ra ngoài thư mục)."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            bad = z.testzip()
    except (zipfile.BadZipFile, OSError):
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
        f"  Remove-Item -LiteralPath {q(staging)} -Recurse -Force -ErrorAction SilentlyContinue",
        f"  Remove-Item -LiteralPath {q(zip_path)} -Force -ErrorAction SilentlyContinue",
        "  Log 'Đã cập nhật xong'",
        "} catch { Log ('Lỗi cập nhật: ' + $_) }",
        f"Start-Process -FilePath {q(install_dir / EXE_NAME)} -WorkingDirectory {q(install_dir)}",
    ])


def start_apply(zip_path: Path, install_dir: Path, work: Path) -> None:
    """Chạy script cập nhật ở tiến trình riêng (tách khỏi app) rồi app tự thoát để file không bị khóa."""
    if sys.platform != "win32":
        raise UpdateError("Tự cập nhật chỉ có trên bản Windows (.exe)")
    verify_zip(zip_path)
    work.mkdir(parents=True, exist_ok=True)
    script = work / "apply.ps1"
    script.write_text(apply_script(zip_path, install_dir, os.getpid(), work), encoding="utf-8-sig")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                     creationflags=flags, close_fds=True)
