"""Configuration centrale, lue depuis les variables d'environnement (jamais de secret en dur)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Charge un fichier .env local s'il existe (sans dépendance externe)."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name, default)
    if val is not None and val.strip() == "":
        return default
    return val


def normalize_database_url(url: str) -> str:
    """SQLAlchemy a besoin du driver psycopg dans le schéma (Render/Heroku donnent postgres:// ou postgresql://)."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def database_url() -> str:
    url = env("DATABASE_URL")
    if url:
        return normalize_database_url(url)
    # Sur Render, le disque du service gratuit est éphémère : un SQLite silencieux
    # ferait perdre toutes les données à chaque déploiement.
    if env("RENDER"):
        raise RuntimeError(
            "DATABASE_URL est obligatoire sur Render : sans PostgreSQL, "
            "les données disparaissent à chaque déploiement."
        )
    return f"sqlite:///{BASE_DIR / 'data' / 'ecom_os.db'}"


TIMEZONE = env("TIMEZONE", "Europe/Brussels")
LOG_DIR = Path(env("LOG_DIR", str(BASE_DIR / "logs")))
