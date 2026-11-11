"""État central : paramètres (arrêt d'urgence, budgets, mode auto)."""
from sqlalchemy.orm import Session

from ..models import Setting

DEFAULT_SETTINGS = {
    "emergency_stop": False,          # STOP ALL
    "auto_mode": False,               # AUTO MODE : pipeline quotidien planifié
    "level_b_enabled": False,         # niveau B actif seulement après configuration explicite
    "budget_ads_eur": 0.0,            # budget pub autorisé (0 € par défaut)
    "budget_purchase_eur": 0.0,       # budget achats fournisseurs autorisé
    "sensitive_price_change_pct": 10.0,  # au-delà : changement de prix = niveau C
    "vat_rate": 0.21,                 # TVA belge standard
    "payment_fee_pct": 0.029,         # hypothèse modifiable (vérifier vos tarifs réels)
    "payment_fee_fixed": 0.25,
    "daily_pipeline_hour": 7,
}


def get_setting(session: Session, key: str):
    row = session.get(Setting, key)
    if row is None:
        return DEFAULT_SETTINGS.get(key)
    return row.value


def set_setting(session: Session, key: str, value) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    session.flush()


def all_settings(session: Session) -> dict:
    out = dict(DEFAULT_SETTINGS)
    for row in session.query(Setting).all():
        out[row.key] = row.value
    return out


def is_stopped(session: Session) -> bool:
    return bool(get_setting(session, "emergency_stop"))
