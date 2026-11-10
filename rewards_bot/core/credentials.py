"""Email + mật khẩu tài khoản Microsoft để bot tự đăng nhập lại khi phiên hết hạn.

Mật khẩu được mã hóa bằng Windows DPAPI (CryptProtectData, phạm vi người dùng hiện tại): chỉ chính tài khoản Windows
này trên chính máy này giải mã được; copy file credentials.json sang máy khác hay user khác thì vô dụng. Không có
DPAPI (Linux/macOS) thì tính năng tắt hẳn, KHÔNG lưu mật khẩu dạng chữ thường.
Giao diện chỉ được biết tài khoản nào đã lưu và email, không bao giờ nhận lại mật khẩu.
"""

import base64
import sys
import threading

from . import config
from .config import read_json, write_json

_LOCK = threading.Lock()
_ENTROPY = b"rewards-bot/credentials/v1"  # thêm vào DPAPI: chương trình khác dùng DPAPI mặc định không giải mã được


class Unsupported(RuntimeError):
    pass


def supported() -> bool:
    return sys.platform == "win32"


def _blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf, DATA_BLOB


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    if not supported():
        raise Unsupported("Chỉ lưu được mật khẩu trên Windows (mã hóa DPAPI)")
    import ctypes
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    src, _keep, DATA_BLOB = _blob(data)
    ent, _keep2, _ = _blob(_ENTROPY)
    out = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1  # không bao giờ hiện hộp thoại
    if encrypt:
        ok = crypt32.CryptProtectData(ctypes.byref(src), "rewards-bot", ctypes.byref(ent), None, None,
                                      CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(src), None, ctypes.byref(ent), None, None,
                                        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
    if not ok:
        raise OSError(f"DPAPI lỗi ({ctypes.GetLastError()})")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def protect(text: str) -> str:
    return base64.b64encode(_dpapi(text.encode("utf-8"), True)).decode("ascii")


def unprotect(token: str) -> str:
    return _dpapi(base64.b64decode(token), False).decode("utf-8")


def save(name: str, email: str, password: str, path=None) -> None:
    path = path or config.CREDENTIALS_FILE
    email = (email or "").strip()
    if "@" not in email or len(email) > 200 or not password or len(password) > 256:
        raise ValueError("Email hoặc mật khẩu không hợp lệ")
    token = protect(password)
    with _LOCK:
        data = read_json(path, {})
        data[name] = {"email": email, "password": token}
        write_json(path, data)
        path.with_suffix(path.suffix + ".bak").unlink(missing_ok=True)  # không để bản cũ chứa mật khẩu cũ


def remove(name: str, path=None) -> None:
    path = path or config.CREDENTIALS_FILE
    with _LOCK:
        data = read_json(path, {})
        if data.pop(name, None) is not None:
            write_json(path, data)
            path.with_suffix(path.suffix + ".bak").unlink(missing_ok=True)


def rename(old: str, new: str, path=None) -> None:
    path = path or config.CREDENTIALS_FILE
    with _LOCK:
        data = read_json(path, {})
        if old in data and old != new:
            data[new] = data.pop(old)
            write_json(path, data)
            path.with_suffix(path.suffix + ".bak").unlink(missing_ok=True)


def emails(path=None) -> dict:
    """{tên tài khoản: email} của các tài khoản đã lưu mật khẩu (không giải mã gì)."""
    data = read_json(path or config.CREDENTIALS_FILE, {})
    return {k: v.get("email", "") for k, v in data.items() if isinstance(v, dict)}


def load(name: str, path=None):
    """(email, mật khẩu) đã giải mã, hoặc None nếu chưa lưu / không giải mã được (khác user Windows, khác máy)."""
    entry = read_json(path or config.CREDENTIALS_FILE, {}).get(name)
    if not isinstance(entry, dict) or not supported():
        return None
    try:
        return entry["email"], unprotect(entry["password"])
    except (KeyError, ValueError, OSError):
        return None


# ---------------------------------------------------------------- bí mật khác, file riêng
# Chỉ còn dùng để xóa token GitHub cũ (bản có tự cập nhật đã lưu nó vào đây).
def remove_secret(key: str, path=None) -> None:
    path = path or config.SECRETS_FILE
    with _LOCK:
        data = read_json(path, {})
        if data.pop(key, None) is not None:
            write_json(path, data)
            path.with_suffix(path.suffix + ".bak").unlink(missing_ok=True)
