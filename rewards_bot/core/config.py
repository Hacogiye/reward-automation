import copy
import json
import os
import sys
from pathlib import Path

# FROZEN: đang chạy từ bản đóng gói PrixAuto.exe (PyInstaller)
FROZEN = bool(getattr(sys, "frozen", False))
# thư mục gốc: bản mã nguồn = thư mục dự án (chứa rewards_bot/ và data/); bản .exe = thư mục chứa PrixAuto.exe
# (không dùng thư mục tạm của PyInstaller, nếu không cập nhật/giải nén lại là mất data/)
BASE_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE = DATA_DIR / "search_history.json"
POINTS_HISTORY_FILE = DATA_DIR / "points_history.json"  # số liệu điểm theo ngày cho biểu đồ
DASHBOARD_FILE = DATA_DIR / "dashboard.json"  # điểm + trạng thái task lần cuối, để mở app là thấy ngay
LOG_DIR = DATA_DIR / "logs"  # nhật ký mỗi ngày 1 file
LOCK_FILE = DATA_DIR / "app.lock"  # chỉ cho 1 cửa sổ app chạy cùng lúc
VISUAL_TRIES_FILE = DATA_DIR / "visual_tries.json"  # số lần thử Visual Search mỗi tài khoản trong ngày
CREDENTIALS_FILE = DATA_DIR / "credentials.json"  # email + mật khẩu đã mã hóa (DPAPI) để tự đăng nhập lại
SECRETS_FILE = DATA_DIR / "secrets.json"  # bí mật khác (đã mã hóa DPAPI); hiện chưa dùng
AVATAR_DIR = DATA_DIR / "avatars"  # ảnh đại diện tài khoản: <thư mục profile>.webp|png|jpg

DEFAULT_SETTINGS = {
    "search_delay_min": 8,
    "search_delay_max": 20,
    "extra_searches": 2,
    "search_browse": True,  # trong lúc chờ lượt search kế: cuộn trang kết quả, đôi khi bấm vào một kết quả
    "search_click_pct": 40,  # % số lượt search có bấm vào một kết quả (khi bật search_browse)
    "stall_after": 6,  # số lượt search liên tiếp không được cộng điểm thì dừng loại search đó
    "visual_max_tries": 4,  # số lần thử Visual Search tối đa mỗi tài khoản mỗi ngày
    "log_keep_days": 14,  # giữ file nhật ký data/logs bao nhiêu ngày
    "browser_channel": "msedge",
    "headless": False,
    "max_parallel": 3,
    "history_days": 30,
    "do_quests": True,  # Daily Set + Keep earning (tên cũ, giữ để không mất cài đặt)
    "do_quest_tasks": True,  # Quests nhiều bước (mục "Quests" ở trang Earn)
    "do_pc": True,
    "do_mobile": True,
    "custom_searches": False,  # tự chọn số lượt search mỗi ngày thay vì search đến khi đủ điểm tối đa
    "pc_searches": 30,  # số lượt search PC trong ngày khi bật custom_searches (3 điểm/lượt)
    "mobile_searches": 20,  # số lượt search Mobile trong ngày khi bật custom_searches
    "do_checkin": True,  # check-in app điện thoại mỗi ngày (Bing App Streak), gọi thẳng DAPI
    "do_read_earn": True,  # Read to Earn: "đọc" tối đa 10 bài báo/ngày qua DAPI (3 điểm/bài)
    "do_visual": True,  # Visual Search: tải 1 ảnh lên bằng nút camera của Bing Images
    "do_browse": False,
    "language": "vi",  # ngôn ngữ giao diện: "vi" / "en" (nhật ký của bot vẫn tiếng Việt)
    "fun_mode": False,  # chế độ vui: trang Văn phòng robot, skin Cyberpunk, icon 3D (tắt = giao diện gọn, icon nét)
    "theme": "system",  # giao diện: "system" (theo Windows) / "light" / "dark" / "cyberpunk"
    "bypass_proxy": True,  # trình duyệt của bot không đi qua proxy hệ thống
    "browse_minutes": 30,
    "browse_auto_stop": True,  # Browse tự dừng khi Edge – Minutes không tăng sau 20 phút
    "onboarded": False,  # đã xem màn hình chào lần đầu (chọn ngôn ngữ, đồng ý rủi ro, thêm tài khoản)
    # phiên bản app lúc người dùng đồng ý phần rủi ro; rỗng = chưa đồng ý, nút Chạy trong giao diện mở lại bước đồng ý.
    # Chỉ chặn giao diện: lệnh --run-all của Task Scheduler không bị ảnh hưởng.
    "risk_ack": "",
    # mục tiêu đổi quà của từng tài khoản: {"tên tài khoản": {"title": "Thẻ quà 5$", "points": 6500}}
    "goals": {},
    # mode: "managed" = cửa sổ riêng do app mở (data/profiles/<dir>)
    #       "cdp"     = gắn vào trình duyệt đang mở với --remote-debugging-port
    # dir: tên thư mục phiên đăng nhập, cố định từ lúc tạo (đổi tên tài khoản không đổi thư mục)
    "profiles": [],
}

# lỗi đọc file gần nhất (để giao diện / log báo cho người dùng thay vì âm thầm reset)
LOAD_WARNINGS: list = []


# ---------------------------------------------------------------- đọc/ghi JSON an toàn
def write_json(path: Path, data, indent=None) -> None:
    """Ghi atomic: ghi ra file tạm rồi thay thế; bản cũ được giữ ở <file>.bak."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.flush()
        os.fsync(f.fileno())
    if path.exists():
        os.replace(path, path.with_suffix(path.suffix + ".bak"))
    os.replace(tmp, path)


def read_json(path: Path, default):
    """Đọc JSON; file hỏng thì dùng <file>.bak và ghi cảnh báo; không có gì thì trả default."""
    for p in (path, path.with_suffix(path.suffix + ".bak")):
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if p != path:
                LOAD_WARNINGS.append(f"{path.name} bị hỏng, đã khôi phục từ bản sao lưu")
            return data
        except Exception:
            if p == path:
                LOAD_WARNINGS.append(f"{path.name} bị hỏng")
    return copy.deepcopy(default)


# ---------------------------------------------------------------- thư mục profile
def safe_dir_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip() or "profile"


def new_profile_dir(name: str, taken=()) -> str:
    """Tên thư mục mới chưa ai dùng cho tài khoản `name`."""
    base = safe_dir_name(name)
    used = set(taken)
    cand, i = base, 2
    while cand in used or (PROFILES_DIR / cand).exists():
        cand, i = f"{base}_{i}", i + 1
    return cand


def profile_dir(profile) -> Path:
    """Thư mục phiên đăng nhập của 1 profile (dict có 'dir'; chuỗi = cách cũ suy ra từ tên)."""
    if isinstance(profile, dict):
        return PROFILES_DIR / (profile.get("dir") or safe_dir_name(profile["name"]))
    return PROFILES_DIR / safe_dir_name(profile)


def _migrate(s: dict) -> bool:
    """Profile cũ chưa có 'dir' -> gán thư mục đang dùng (suy từ tên). Trả True nếu có thay đổi."""
    changed = False
    for p in s.get("profiles", []):
        if not p.get("dir"):
            p["dir"] = safe_dir_name(p["name"])
            changed = True
    return changed


# ---------------------------------------------------------------- cài đặt
def load_settings() -> dict:
    s = copy.deepcopy(DEFAULT_SETTINGS)
    s.update(read_json(SETTINGS_FILE, {}))
    if _migrate(s):
        save_settings(s)
    return s


def save_settings(s: dict) -> None:
    write_json(SETTINGS_FILE, s, indent=2)
