"""Mở Edge/Chrome "thường" cho bot rồi để Playwright gắn vào qua CDP (giống cách Selenium chạy).

Vì sao không dùng launch_persistent_context của Playwright: nó thêm khoảng 40 cờ (--enable-automation,
--disable-background-networking, --disable-sync, ...) và đặt navigator.webdriver = true. Với các cờ đó Bing từ chối
Visual Search ("Unable to process this search", upload trả 400). Mở trình duyệt chỉ với vài cờ tối thiểu thì
Visual Search chạy được và navigator.webdriver = false.

Cổng debug: --remote-debugging-port=0 để trình duyệt tự chọn cổng trống, chỉ nghe trên 127.0.0.1, đọc cổng từ file
DevToolsActivePort trong thư mục profile. Cổng đóng cùng trình duyệt.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Cờ đánh dấu trình duyệt do bot mở (để nhận ra bản mồ côi sau khi app bị tắt giữa chừng)
BOT_MARKER = "--remote-debugging-port=0"

_CANDIDATES = {  # Windows: đường dẫn tương đối trong Program Files / LocalAppData
    "msedge": [r"Microsoft\Edge\Application\msedge.exe"],
    "chrome": [r"Google\Chrome\Application\chrome.exe"],
}
# Linux / macOS: tên lệnh trên PATH và vị trí cài mặc định
_UNIX_NAMES = {
    "msedge": ["microsoft-edge-stable", "microsoft-edge", "microsoft-edge-beta", "microsoft-edge-dev", "msedge"],
    "chrome": ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser"],
}
_UNIX_PATHS = {
    "msedge": ["/opt/microsoft/msedge/msedge", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
    "chrome": ["/opt/google/chrome/chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
}
# phần hệ điều hành trong User-Agent, giống trình duyệt thật trên từng nền tảng
_UA_PLATFORM = {"win32": "Windows NT 10.0; Win64; x64", "darwin": "Macintosh; Intel Mac OS X 10_15_7"}
_UA_PLATFORM_DEFAULT = "X11; Linux x86_64"


class LaunchError(RuntimeError):
    pass


def find_browser(channel: str) -> str:
    """Đường dẫn file chạy của trình duyệt theo kênh ("msedge" / "chrome" / "" = Chromium của Playwright)."""
    if not channel:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            path = p.chromium.executable_path
        if path and os.path.exists(path):
            return path
        raise LaunchError("Chưa cài Chromium của Playwright. Chạy: python -m playwright install chromium")
    if sys.platform == "win32":
        roots = [os.environ.get(k) for k in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
        for rel in _CANDIDATES.get(channel, []):
            for root in filter(None, roots):
                path = os.path.join(root, rel)
                if os.path.exists(path):
                    return path
    else:
        for name in _UNIX_NAMES.get(channel, []):
            found = shutil.which(name)
            if found:
                return found
        for path in _UNIX_PATHS.get(channel, []):
            if os.path.exists(path):
                return path
    found = shutil.which(channel)
    if found:
        return found
    hint = {"msedge": "Edge (gói microsoft-edge-stable)", "chrome": "Google Chrome hoặc Chromium"}.get(channel, channel)
    raise LaunchError(f"Không tìm thấy trình duyệt '{channel}' trên máy. Cài {hint} hoặc chọn trình duyệt khác trong Cài đặt")


def _version_from_folder(exe: str):
    """Windows: thư mục phiên bản (vd 155.0.4283.62) nằm cạnh msedge.exe / chrome.exe."""
    folder = os.path.dirname(exe)
    try:
        versions = [d for d in os.listdir(folder) if d[:1].isdigit() and d.count(".") == 3]
    except OSError:
        return None
    return max(versions, key=lambda v: tuple(int(x) for x in v.split("."))).split(".")[0] if versions else None


def parse_version_output(text: str):
    """Số phiên bản chính từ kết quả `--version`, vd "Microsoft Edge 155.0.4283.62" -> "155"."""
    m = re.search(r"(\d+)\.\d+\.\d+(?:\.\d+)?", text or "")
    return m.group(1) if m else None


def browser_version(exe: str):
    """Số phiên bản chính (vd "155") của trình duyệt."""
    major = _version_from_folder(exe)
    if major or sys.platform == "win32":  # trên Windows, msedge.exe --version không in gì ra
        return major
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version_output(out)


def normal_user_agent(exe: str):
    """User-Agent của trình duyệt chạy bình thường. Chạy ẩn thì Edge tự ghi "HeadlessChrome" và Bing từ chối Visual Search."""
    major = browser_version(exe)
    if not major:
        return None
    platform = _UA_PLATFORM.get(sys.platform, _UA_PLATFORM_DEFAULT)
    ua = f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
    return ua + f" Edg/{major}.0.0.0" if is_edge(exe) else ua


def is_edge(exe: str) -> bool:
    name = os.path.basename(exe).lower()
    return name.startswith("msedge") or "microsoft-edge" in name or name == "microsoft edge"


# Một thư mục dữ liệu có thể chứa nhiều profile Edge (Default, Profile 1, ...), mỗi profile đăng nhập trình duyệt
# bằng một tài khoản khác. Không chỉ định thì Edge mở profile dùng gần nhất, nên bot có thể lặng lẽ chạy sai profile.
# Bot ghim profile vào file này ở lần mở đầu tiên rồi luôn mở đúng profile đó (--profile-directory).
PIN_FILE = "rewards_bot_profile.txt"
_PROFILE_DIR_RE = re.compile(r"^(Default|Profile \d{1,3})$")


def _info_cache(user_data_dir: str) -> dict:
    try:
        cache = json.loads((Path(user_data_dir) / "Local State").read_text(encoding="utf-8"))["profile"]["info_cache"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {k: v for k, v in cache.items() if _PROFILE_DIR_RE.match(k) and isinstance(v, dict)} \
        if isinstance(cache, dict) else {}


def edge_profiles(user_data_dir: str) -> dict:
    """Các profile Edge trong thư mục: {"Profile 1": "email hoặc tên"} (đọc từ file Local State)."""
    return {k: (v.get("user_name") or v.get("name") or "") for k, v in _info_cache(user_data_dir).items()}


def signed_in_profiles(user_data_dir: str) -> dict:
    """Chỉ các profile đã đăng nhập trình duyệt bằng tài khoản: {"Profile 2": "email"}."""
    return {k: v["user_name"] for k, v in _info_cache(user_data_dir).items() if v.get("user_name")}


def _last_used(user_data_dir: str):
    try:
        name = json.loads((Path(user_data_dir) / "Local State").read_text(encoding="utf-8"))["profile"]["last_used"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return name if isinstance(name, str) and _PROFILE_DIR_RE.match(name) else None


def pinned_profile(user_data_dir: str) -> str:
    """Profile Edge bot luôn dùng trong thư mục này. Lần đầu: ghim profile đang dùng gần nhất (thư mục mới: Default)."""
    f = Path(user_data_dir) / PIN_FILE
    try:
        name = f.read_text(encoding="utf-8").strip()
    except OSError:
        name = ""
    if not _PROFILE_DIR_RE.match(name):
        name = _last_used(user_data_dir) or "Default"
        try:
            f.write_text(name + "\n", encoding="utf-8")
        except OSError:
            pass
    return name


def repin_to_last_used(user_data_dir: str):
    """Sau khi người dùng tự đăng nhập: nếu họ đã chuyển sang profile Edge khác trong cửa sổ đó thì ghim profile ấy.

    Trả (cũ, mới) khi đổi ghim, None nếu giữ nguyên."""
    old = pinned_profile(user_data_dir)
    new = _last_used(user_data_dir)
    if not new or new == old or not (Path(user_data_dir) / new).is_dir():
        return None
    try:
        (Path(user_data_dir) / PIN_FILE).write_text(new + "\n", encoding="utf-8")
    except OSError:
        return None
    return old, new


def build_args(exe: str, user_data_dir: str, headless: bool, extra=(), profile_directory: str = None) -> list:
    """Dòng lệnh mở trình duyệt: chỉ các cờ cần thiết, không có cờ tự động hóa."""
    args = [exe, f"--user-data-dir={user_data_dir}", BOT_MARKER, "--remote-debugging-address=127.0.0.1",
            "--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check",
            "--window-size=1366,900", *extra]
    if profile_directory:
        if not _PROFILE_DIR_RE.match(profile_directory):
            raise ValueError(f"Tên profile Edge không hợp lệ: {profile_directory!r}")
        args.append(f"--profile-directory={profile_directory}")
    if os.path.basename(exe).lower() == "msedge.exe":  # chỉ Edge trên Windows mới tự mở lại qua lớp tương thích
        args.append("--edge-skip-compat-layer-relaunch")  # để Edge không tự mở lại thành process khác
    if headless:
        # cửa sổ ẩn hẳn ra ngoài màn hình; KHÔNG thêm --disable-gpu (theo AutoRewarder, cờ đó làm hỏng việc đếm phút Edge)
        args += ["--headless=new", "--window-position=-32000,-32000", "--screen-info={0,0 1920x1080}"]
        ua = normal_user_agent(exe)
        if ua:
            args.append(f"--user-agent={ua}")
    return args + ["about:blank"]


def read_port(user_data_dir: str):
    """Cổng debug trình duyệt ghi ra (dòng đầu của DevToolsActivePort), None nếu chưa có."""
    f = Path(user_data_dir) / "DevToolsActivePort"
    try:
        first = f.read_text(encoding="utf-8").splitlines()[0].strip()
        return int(first) if first.isdigit() else None
    except (OSError, IndexError):
        return None


class Launched:
    """Trình duyệt bot đã mở: process + địa chỉ CDP."""

    def __init__(self, proc: subprocess.Popen, cdp_url: str):
        self.proc = proc
        self.cdp_url = cdp_url

    def alive(self) -> bool:
        return self.proc.poll() is None

    def kill(self) -> None:
        """Buộc đóng (dùng từ thread khác khi bấm Dừng; Playwright không gọi được từ thread khác)."""
        try:
            self.proc.kill()
        except OSError:
            pass

    def close(self, browser=None, timeout: float = 10) -> None:
        """Đóng trình duyệt gọn gàng (để kịp lưu cookie / phiên đăng nhập), quá lâu thì buộc đóng."""
        if browser is not None:
            try:
                browser.new_browser_cdp_session().send("Browser.close")
            except Exception:
                pass
        try:
            self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                pass


def launch(channel: str, user_data_dir: str, headless: bool, extra=(), timeout: float = 30,
           profile_directory: str = None) -> Launched:
    exe = find_browser(channel)
    (Path(user_data_dir) / "DevToolsActivePort").unlink(missing_ok=True)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    proc = subprocess.Popen(build_args(exe, user_data_dir, headless, extra, profile_directory), creationflags=flags,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        port = read_port(user_data_dir)
        if port:
            return Launched(proc, f"http://127.0.0.1:{port}")
        if proc.poll() is not None:
            raise LaunchError("Trình duyệt đóng ngay khi mở (profile có thể đang mở ở cửa sổ khác)")
        time.sleep(0.2)
    proc.kill()
    raise LaunchError("Trình duyệt không mở cổng điều khiển sau 30 giây")
