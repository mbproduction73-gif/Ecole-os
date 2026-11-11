"""Journalisation : fichier + table action_log (historique des actions)."""
import logging
from logging.handlers import RotatingFileHandler

from sqlalchemy.orm import Session

from .. import config
from ..models import ActionLog

_logger = None

OUTCOMES = {"execute", "prepare", "bloque", "approbation_requise", "non_connecte", "erreur", "info"}


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger("ecom_os")
        _logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        _logger.addHandler(sh)
        try:
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(config.LOG_DIR / "ecom_os.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
            fh.setFormatter(fmt)
            _logger.addHandler(fh)
        except OSError:
            pass
    return _logger


def log_action(session: Session, agent: str, action: str, outcome: str, message: str = "",
               level: str | None = None, details: dict | None = None, spend_eur: float = 0.0) -> ActionLog:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome inconnu: {outcome}")
    entry = ActionLog(agent=agent, action=action, outcome=outcome, message=message,
                      level=level, details=details or {}, spend_eur=spend_eur)
    session.add(entry)
    session.flush()
    get_logger().info("[%s] %s -> %s : %s", agent, action, outcome, message)
    return entry
