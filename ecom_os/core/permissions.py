"""Moteur d'autorisations — niveaux A / B / C.

A : autonomie complète sans dépense (recherche, analyse, brouillons, rapports).
B : exécution contrôlée et réversible, uniquement après configuration (level_b_enabled).
C : validation humaine obligatoire. Toute action C crée une approbation en attente
    et ne s'exécute JAMAIS sans approbation explicite correspondante.
STOP ALL (emergency_stop) bloque toute nouvelle action, quel que soit le niveau.
Une action inconnue est traitée comme niveau C (principe de prudence).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Approval
from .logs import log_action
from .state import get_setting, is_stopped

LEVEL_A = {
    "research", "analyze", "score_products", "compare_suppliers", "create_draft",
    "generate_content", "prepare_store", "report", "monitor", "import_csv",
    "prepare_supplier_request", "prepare_ad_campaign", "read_connector",
}
LEVEL_B = {
    "publish_product_draft", "publish_product", "update_stock", "edit_page",
    "publish_organic_post", "reply_customer_simple", "price_change_minor",
}
LEVEL_C = {
    "ad_spend", "supplier_purchase", "payment", "contract", "bank_details_change",
    "sensitive_price_change", "refund", "permanent_delete", "first_public_launch",
}
# Actions dont le montant est plafonné par un budget
BUDGETED = {"ad_spend": "budget_ads_eur", "supplier_purchase": "budget_purchase_eur", "payment": "budget_purchase_eur"}


def level_of(action: str) -> str:
    if action in LEVEL_A:
        return "A"
    if action in LEVEL_B:
        return "B"
    return "C"  # LEVEL_C + toute action inconnue


def classify_price_change(session: Session, old_price: float, new_price: float) -> str:
    """Retourne l'action correspondant à un changement de prix (mineur = B, sensible = C)."""
    if not old_price:
        return "sensitive_price_change"
    pct = abs(new_price - old_price) / old_price * 100
    threshold = float(get_setting(session, "sensitive_price_change_pct") or 10)
    return "sensitive_price_change" if pct > threshold else "price_change_minor"


@dataclass
class Decision:
    allowed: bool
    level: str
    status: str  # autorise / bloque_stop / bloque_config / approbation_requise / refuse
    reason: str
    approval_id: int | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return {"allowed": self.allowed, "level": self.level, "status": self.status,
                "reason": self.reason, "approval_id": self.approval_id, **self.extra}


def authorize(session: Session, action: str, agent: str = "systeme", payload: dict | None = None,
              approval_id: int | None = None, amount_eur: float | None = None) -> Decision:
    """Décide si une action peut s'exécuter maintenant. Journalise la décision."""
    level = level_of(action)
    payload = payload or {}

    if is_stopped(session):
        d = Decision(False, level, "bloque_stop", "STOP ALL actif : aucune nouvelle action n'est autorisée.")
        log_action(session, agent, action, "bloque", d.reason, level=level, details=payload)
        return d

    if level == "A":
        return Decision(True, "A", "autorise", "Niveau A : autonome, sans dépense.")

    if level == "B":
        if not get_setting(session, "level_b_enabled"):
            d = Decision(False, "B", "bloque_config",
                         "Niveau B désactivé : activez-le dans Paramètres après configuration.")
            log_action(session, agent, action, "bloque", d.reason, level="B", details=payload)
            return d
        return Decision(True, "B", "autorise", "Niveau B : action réversible autorisée par la configuration.")

    # Niveau C
    if approval_id is not None:
        appr = session.get(Approval, approval_id)
        if appr is None or appr.action != action:
            d = Decision(False, "C", "refuse", "Approbation introuvable ou ne correspondant pas à cette action.")
            log_action(session, agent, action, "bloque", d.reason, level="C", details=payload)
            return d
        if appr.status == "approuve":
            return Decision(True, "C", "autorise", "Approuvé explicitement par le propriétaire.", approval_id=appr.id)
        d = Decision(False, "C", "refuse", f"Approbation au statut « {appr.status} » : exécution impossible.",
                     approval_id=appr.id)
        log_action(session, agent, action, "bloque", d.reason, level="C", details=payload)
        return d

    appr = Approval(action=action, level="C", payload=payload, amount_eur=amount_eur,
                    status="en_attente", requested_by=agent,
                    reason=payload.get("reason") if isinstance(payload, dict) else None)
    session.add(appr)
    session.flush()
    d = Decision(False, "C", "approbation_requise",
                 "Niveau C : validation humaine obligatoire. Approbation créée.", approval_id=appr.id)
    log_action(session, agent, action, "approbation_requise", d.reason, level="C",
               details={"approval_id": appr.id, **payload})
    return d


def approve(session: Session, approval_id: int, note: str = "") -> Approval:
    appr = session.get(Approval, approval_id)
    if appr is None:
        raise LookupError("Approbation introuvable")
    if appr.status != "en_attente":
        raise ValueError(f"Approbation déjà au statut « {appr.status} »")
    if is_stopped(session):
        raise PermissionError("STOP ALL actif : désactivez-le avant d'approuver.")
    budget_key = BUDGETED.get(appr.action)
    if budget_key and appr.amount_eur is not None:
        budget = float(get_setting(session, budget_key) or 0)
        if appr.amount_eur > budget:
            raise ValueError(f"Montant {appr.amount_eur:.2f} € supérieur au budget autorisé "
                             f"({budget:.2f} €, paramètre {budget_key}). Augmentez d'abord le budget.")
    appr.status = "approuve"
    appr.decision_note = note
    appr.decided_at = datetime.now(timezone.utc)
    log_action(session, "proprietaire", appr.action, "info", f"Approbation #{appr.id} accordée", level="C")
    return appr


def reject(session: Session, approval_id: int, note: str = "") -> Approval:
    appr = session.get(Approval, approval_id)
    if appr is None:
        raise LookupError("Approbation introuvable")
    if appr.status != "en_attente":
        raise ValueError(f"Approbation déjà au statut « {appr.status} »")
    appr.status = "refuse"
    appr.decision_note = note
    appr.decided_at = datetime.now(timezone.utc)
    log_action(session, "proprietaire", appr.action, "info", f"Approbation #{appr.id} refusée", level="C")
    return appr


def mark_executed(session: Session, approval_id: int) -> None:
    """Une approbation ne sert qu'une fois."""
    appr = session.get(Approval, approval_id)
    if appr and appr.status == "approuve":
        appr.status = "execute"


def run_guarded(session: Session, action: str, func, *, agent: str = "systeme", payload: dict | None = None,
                approval_id: int | None = None, amount_eur: float | None = None, spend_eur: float = 0.0):
    """Exécute func() uniquement si autorisé. Retourne (Decision, résultat|None)."""
    d = authorize(session, action, agent=agent, payload=payload, approval_id=approval_id, amount_eur=amount_eur)
    if not d.allowed:
        return d, None
    result = func()
    if d.level == "C" and d.approval_id:
        mark_executed(session, d.approval_id)
    log_action(session, agent, action, "execute", d.reason, level=d.level, details=payload, spend_eur=spend_eur)
    return d, result
