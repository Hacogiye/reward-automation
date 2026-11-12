import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Chuyển toàn bộ đường dẫn data/ sang thư mục tạm để test không đụng dữ liệu thật."""
    from rewards_bot.core import config
    d = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", d)
    monkeypatch.setattr(config, "PROFILES_DIR", d / "profiles")
    monkeypatch.setattr(config, "SETTINGS_FILE", d / "settings.json")
    monkeypatch.setattr(config, "LOG_DIR", d / "logs")
    monkeypatch.setattr(config, "LOCK_FILE", d / "app.lock")
    monkeypatch.setattr(config, "CREDENTIALS_FILE", d / "credentials.json")
    monkeypatch.setattr(config, "SECRETS_FILE", d / "secrets.json")
    monkeypatch.setattr(config, "AVATAR_DIR", d / "avatars")
    monkeypatch.setattr(config, "UPDATE_DIR", d / "update")
    config.LOAD_WARNINGS.clear()
    return d
