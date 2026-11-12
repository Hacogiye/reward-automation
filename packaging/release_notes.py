"""Ghi chú cho GitHub Release, lấy từ CHANGELOG.md (app hiện nó làm "danh sách thay đổi" khi báo có bản mới).

    python packaging/release_notes.py v1.7.3 > notes.md

Mỗi phiên bản BẮT BUỘC có mục `## X.Y.Z - YYYY-MM-DD` trong CHANGELOG.md. Thiếu mục hoặc mục rỗng thì thoát lỗi, nên
workflow release.yml dừng trước khi build và không tạo bản phát hành nào.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
HEAD_RE = re.compile(r"^##\s+v?(\d+\.\d+\.\d+)\b.*$", re.M)


def section(version: str, text: str):
    """Nội dung mục `## <version>` (tới mục `## ` kế tiếp), đã bỏ dòng trống đầu/cuối; không có thì None."""
    heads = list(HEAD_RE.finditer(text))
    for i, m in enumerate(heads):
        if m.group(1) == version:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            body = text[m.end():end].strip()
            return body or None
    return None


def previous_tag(tag: str) -> str:
    """Tag vX.Y.Z gần nhất trước `tag` (rỗng nếu đây là tag đầu tiên hoặc không có git)."""
    try:
        return subprocess.run(["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", f"{tag}^"], check=True,
                              capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return ""


def build(tag: str, text: str, prev: str = "") -> str:
    version = tag.lstrip("v")
    body = section(version, text)
    if not body:
        raise ValueError(f"CHANGELOG.md chưa có mục '## {version} - <ngày>' (hoặc mục rỗng): viết danh sách thay đổi "
                         f"cho người dùng trước khi phát hành {tag}")
    return body + (f"\n\nSo sánh / Compare: {prev}...{tag}" if prev else "") + "\n"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Dùng: python packaging/release_notes.py vX.Y.Z")
    tag = sys.argv[1]
    sys.stderr.reconfigure(encoding="utf-8")  # thông báo lỗi tiếng Việt không bị vỡ chữ trên console Windows
    try:
        notes = build(tag, CHANGELOG.read_text(encoding="utf-8"), previous_tag(tag))
    except (ValueError, OSError) as e:
        sys.exit(f"Lỗi: {e}")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(notes)


if __name__ == "__main__":
    main()
