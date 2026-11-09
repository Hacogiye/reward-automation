"""Build bản Windows: dist/PrixAuto/PrixAuto.exe và file nén dist/PrixAuto-<phiên bản>-win64.zip (để gửi cho người dùng).

    pip install -r requirements-dev.txt
    python packaging/build_exe.py
"""
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rewards_bot import __version__  # noqa: E402

DIST, WORK = ROOT / "dist", ROOT / "build"


def main() -> None:
    if sys.platform != "win32":
        sys.exit("Chỉ build bản .exe trên Windows")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(DIST),
                    "--workpath", str(WORK), str(ROOT / "packaging" / "PrixAuto.spec")], check=True)
    app = DIST / "PrixAuto"
    if not (app / "PrixAuto.exe").exists():
        sys.exit("Build lỗi: không thấy PrixAuto.exe")
    out = DIST / f"PrixAuto-{__version__}-win64.zip"
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(app.rglob("*")):
            rel = f.relative_to(DIST)
            if f.is_file() and rel.parts[1:2] != ("data",):  # không bao giờ đóng gói data/ (phiên đăng nhập)
                z.write(f, rel.as_posix())
    print(f"Xong: {app / 'PrixAuto.exe'}\n      {out} ({out.stat().st_size / 1048576:.1f} MB)")


if __name__ == "__main__":
    main()
