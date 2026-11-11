"""Accès base de données : SQLite par défaut, PostgreSQL via DATABASE_URL."""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _make_engine(url: str):
    url = config.normalize_database_url(url)
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            from sqlalchemy.pool import StaticPool
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def configure(url: str | None = None):
    """(Re)configure le moteur. Utilisé au démarrage et dans les tests."""
    global _engine, _SessionLocal
    url = url or config.database_url()
    if url.startswith("sqlite:///") and ":memory:" not in url:
        from pathlib import Path
        Path(url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    _engine = _make_engine(url)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    from . import models  # noqa: F401  (enregistre les tables)
    Base.metadata.create_all(_engine)
    return _engine


def get_engine():
    if _engine is None:
        configure()
    return _engine


def SessionLocal():
    if _SessionLocal is None:
        configure()
    return _SessionLocal()


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session():
    """Dépendance FastAPI."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
