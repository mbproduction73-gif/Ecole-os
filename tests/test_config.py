import pytest

from ecom_os.config import database_url, normalize_database_url


def test_normalize_postgres_schemes():
    assert normalize_database_url("postgres://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert normalize_database_url("postgresql://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    already = "postgresql+psycopg://u:p@host:5432/db"
    assert normalize_database_url(already) == already
    sqlite = "sqlite:////tmp/ecom_os.db"
    assert normalize_database_url(sqlite) == sqlite


def test_database_url_sqlite_by_default(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert database_url().startswith("sqlite:///")


def test_database_url_required_on_render(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        database_url()


def test_database_url_uses_env_on_render(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    monkeypatch.setenv("RENDER", "true")
    assert database_url() == "postgresql+psycopg://u:p@host/db"
