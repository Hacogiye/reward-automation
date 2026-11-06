"""Các biện pháp bảo vệ cục bộ cho app.

- Khóa quyền thư mục data/ (phiên đăng nhập, cookie) để chỉ tài khoản Windows hiện tại đọc được.
- Phát hiện proxy hệ thống / biến môi trường proxy để cảnh báo (trình duyệt của bot mặc định bỏ qua proxy).
- Kiểm tra cổng debug (CDP) chỉ mở trên localhost, không lộ ra mạng LAN.

Giới hạn: phần mềm độc hại chạy dưới chính tài khoản Windows của bạn vẫn đọc được dữ liệu của bạn;
các biện pháp này chặn người dùng khác trên máy, máy khác trong mạng và proxy chen giữa.
"""

import os
import socket
import subprocess
import sys
from pathlib import Path

PORT_MIN, PORT_MAX = 1024, 65535


def harden_data_dir(data_dir: Path, log=print) -> None:
    """Windows: bỏ quyền kế thừa của data/, chỉ cho user hiện tại + SYSTEM. Chạy 1 lần (có file đánh dấu)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    marker = data_dir / ".acl_hardened"
    if sys.platform != "win32" or marker.exists():
        return
    user = os.environ.get("USERNAME")
    domain = os.environ.get("USERDOMAIN")
    if not user:
        return
    who = f"{domain}\\{user}" if domain else user
    cmd = ["icacls", str(data_dir), "/inheritance:r",
           "/grant:r", f"{who}:(OI)(CI)F", "/grant:r", "*S-1-5-18:(OI)(CI)F"]  # S-1-5-18 = SYSTEM
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0:
            marker.write_text("ok", encoding="utf-8")
            log(f"Đã khóa quyền thư mục dữ liệu: chỉ {who} và SYSTEM truy cập được")
        else:
            log(f"Không khóa được quyền thư mục dữ liệu: {(r.stderr or r.stdout).strip()[:200]}")
    except Exception as e:
        log(f"Không khóa được quyền thư mục dữ liệu: {e}")


def system_proxy() -> str:
    """Trả về mô tả proxy đang bật trên máy (Windows Internet Settings hoặc biến môi trường), rỗng nếu không có."""
    found = []
    for k in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        if os.environ.get(k):
            found.append(f"{k}={os.environ[k]}")
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
                enabled = winreg.QueryValueEx(key, "ProxyEnable")[0]
                if enabled:
                    found.append("Windows proxy: " + str(winreg.QueryValueEx(key, "ProxyServer")[0]))
                try:
                    pac = winreg.QueryValueEx(key, "AutoConfigURL")[0]
                    if pac:
                        found.append("PAC: " + str(pac))
                except OSError:
                    pass
        except OSError:
            pass
    return "; ".join(found)


PROXY_SCHEMES = ("http", "https", "socks4", "socks5")


def validate_proxy(value) -> str:
    """Chuẩn hóa proxy riêng của tài khoản thành "scheme://host:port"; rỗng = không dùng proxy riêng.

    Không nhận user:pass trong địa chỉ: Chromium không đọc mật khẩu từ --proxy-server, và để vậy thì mật khẩu
    sẽ nằm trong dòng lệnh của process (ai trên máy cũng đọc được). Dùng proxy xác thực theo IP.
    """
    s = str(value or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    scheme, rest = s.split("://", 1)
    scheme = scheme.lower()
    if scheme not in PROXY_SCHEMES:
        raise ValueError(f"Proxy phải bắt đầu bằng {', '.join(x + '://' for x in PROXY_SCHEMES)}")
    rest = rest.rstrip("/")
    if "@" in rest:
        raise ValueError("Không hỗ trợ proxy có user:mật khẩu. Dùng proxy xác thực theo IP (whitelist IP máy này)")
    host, sep, port = rest.rpartition(":")
    if not sep or not host or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError("Proxy cần dạng host:cổng, ví dụ socks5://1.2.3.4:1080")
    if host.startswith("[") and host.endswith("]"):  # IPv6
        ok = all(c in "0123456789abcdefABCDEF:." for c in host[1:-1])
    else:
        ok = all(c.isalnum() or c in "-." for c in host)
    if not ok or len(host) > 255:
        raise ValueError("Tên máy proxy không hợp lệ")
    return f"{scheme}://{host}:{int(port)}"


def browser_args(settings: dict, proxy: str = "") -> list:
    """Cờ dòng lệnh an toàn cho trình duyệt do app mở. `proxy`: proxy riêng của tài khoản (đã kiểm tra)."""
    if proxy:
        proxy = validate_proxy(proxy)
        # chỉ đi qua proxy này (không dùng proxy hệ thống); WebRTC không được gửi UDP ra ngoài proxy (lộ IP thật)
        return [f"--proxy-server={proxy}", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]
    args = []
    if settings.get("bypass_proxy", True):
        args += ["--no-proxy-server"]  # không đi qua proxy hệ thống / PAC
    return args


def validate_port(port) -> int:
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError("Cổng debug phải là số")
    if not PORT_MIN <= port <= PORT_MAX:
        raise ValueError(f"Cổng debug phải trong khoảng {PORT_MIN}-{PORT_MAX}")
    return port


def _lan_ip() -> str:
    """IP của máy trong mạng LAN (không gửi gói tin nào ra ngoài)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


def cdp_exposed(port: int) -> bool:
    """True nếu cổng debug nghe trên địa chỉ mạng (máy khác trong LAN kết nối được), không chỉ localhost."""
    ip = _lan_ip()
    if not ip or ip.startswith("127."):
        return False
    try:
        with socket.create_connection((ip, port), timeout=0.5):
            return True
    except OSError:
        return False
