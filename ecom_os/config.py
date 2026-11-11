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


def database_url() -> str:
    return env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'ecom_os.db'}")


TIMEZONE = env("TIMEZONE", "Europe/Brussels")
LOG_DIR = Path(env("LOG_DIR", str(BASE_DIR / "logs")))
