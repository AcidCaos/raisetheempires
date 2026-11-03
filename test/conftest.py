import pytest

import save_engine


@pytest.fixture(autouse=True)
def backup_db(monkeypatch, tmp_path):
    """Keep save game backups made during tests out of the real backups.db."""
    monkeypatch.setattr(save_engine, "backup_db_path", lambda: str(tmp_path / "backups.db"))
    return save_engine
