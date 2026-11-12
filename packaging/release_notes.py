"""Ghi chú cho GitHub Release (app hiện nó làm "Danh sách thay đổi" khi báo có bản mới).

    python packaging/release_notes.py v1.6.0 > notes.md

Lấy các commit từ tag phiên bản trước tới tag này (bỏ commit merge):
- phần thân của commit "Version X.Y.Z" là đoạn tóm tắt ở đầu;
- mỗi commit còn lại là một gạch đầu dòng (tiêu đề commit), dòng "Co-Authored-By" bị bỏ.
"""
import re
import subprocess
import sys

SEP = "\x1e"  # tách các commit trong đầu ra của git log
VERSION_RE = re.compile(r"^(Version|Release|Bump version)\b.*\d+\.\d+", re.I)
TRAILER_RE = re.compile(r"^(Co-Authored-By|Signed-off-by):", re.I)


def _git(*args) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def previous_tag(tag: str) -> str:
    """Tag vX.Y.Z gần nhất trước `tag` (rỗng nếu đây là tag đầu tiên)."""
    try:
        return _git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", f"{tag}^").strip()
    except subprocess.CalledProcessError:
        return ""


def commits(tag: str, prev: str) -> list:
    """[(tiêu đề, thân)] từ cũ tới mới."""
    rng = f"{prev}..{tag}" if prev else tag
    out = _git("log", "--no-merges", "--reverse", f"--format=%s%n%b{SEP}", rng)
    items = []
    for block in out.split(SEP):
        lines = block.strip("\n").splitlines()
        if lines and lines[0].strip():
            items.append((lines[0].strip(), "\n".join(lines[1:])))
    return items


def _clean(body: str) -> str:
    return "\n".join(ln for ln in body.splitlines() if not TRAILER_RE.match(ln.strip())).strip()


def build(tag: str, items: list, prev: str = "") -> str:
    summary = [_clean(b) for s, b in items if VERSION_RE.match(s) and _clean(b)]
    changes = [s for s, _ in items if not VERSION_RE.match(s)]
    parts = []
    if summary:
        parts.append(summary[-1])
    if changes:
        parts.append("### Thay đổi / Changes\n" + "\n".join(f"- {s}" for s in changes))
    if not parts:
        parts.append(f"Phiên bản {tag.lstrip('v')}.")
    if prev:
        parts.append(f"So sánh / Compare: {prev}...{tag}")
    return "\n\n".join(parts) + "\n"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Dùng: python packaging/release_notes.py vX.Y.Z")
    tag = sys.argv[1]
    prev = previous_tag(tag)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(build(tag, commits(tag, prev), prev))


if __name__ == "__main__":
    main()
