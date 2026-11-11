from ecom_os.config import normalize_database_url


def test_normalize_postgres_schemes():
    assert normalize_database_url("postgres://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert normalize_database_url("postgresql://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    already = "postgresql+psycopg://u:p@host:5432/db"
    assert normalize_database_url(already) == already
    sqlite = "sqlite:////tmp/ecom_os.db"
    assert normalize_database_url(sqlite) == sqlite
