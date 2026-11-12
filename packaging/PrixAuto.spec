# PyInstaller: đóng gói thành thư mục PrixAuto/ (PrixAuto.exe + _internal/). Chạy qua: python packaging/build_exe.py
# Bản thư mục (onedir) mở nhanh hơn bản 1 file và ít bị phần mềm diệt virus báo nhầm.
import os
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "rewards_bot" / "ui" / "web"), "rewards_bot/ui/web"),
           (str(ROOT / "rewards_bot" / "search" / "popular_queries.json"), "rewards_bot/search")],
    hiddenimports=["rewards_bot.ui.webapp", "rewards_bot.cli"],
    excludes=["tkinter", "pytest", "rewards_bot.gui"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PrixAuto", console=bool(os.environ.get("RB_CONSOLE")),
          icon=str(ROOT / "rewards_bot" / "ui" / "web" / "assets" / "app-icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="PrixAuto")
