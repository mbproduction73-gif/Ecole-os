"""Agent Director : orchestre le pipeline quotidien (phases 1 à 9) et produit le rapport.

Le rapport sépare strictement : exécuté / préparé / approbation requise / non connecté / erreurs.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.logs import log_action
from ..core.state import is_stopped
from ..models import ActionLog, Approval, Product, ProductDraft, Task
from . import finance, scout, store_builder, supplier

PHASES = [
    (1, "Analyser les tendances et opportunités"),
    (2, "Vérifier les fournisseurs et les stocks"),
    (3, "Sélectionner les meilleurs produits candidats"),
    (4, "Préparer les fiches produits et visuels"),
    (5, "Produire le contenu marketing"),
    (6, "Suivre les ventes et les campagnes"),
    (7, "Détecter les anomalies et problèmes"),
    (8, "Proposer ou réaliser les optimisations autorisées"),
    (9, "Préparer le rapport quotidien"),
]


def _anomalies(session: Session) -> list[str]:
    out = []
    for p in session.query(Product).all():
        if p.offers and p.est_sale_price:
            best = min(p.offers, key=lambda o: o.unit_cost + (o.shipping_cost or 0))
            if best.unit_cost + (best.shipping_cost or 0) >= p.est_sale_price / 1.21:
                out.append(f"« {p.name} » : coût rendu ≥ prix HT (vente à perte)")
        for o in p.offers:
            if o.stock is not None and o.stock < 20:
                out.append(f"« {p.name} » chez {o.supplier.name} : stock faible ({o.stock})")
    pend = session.query(Approval).filter_by(status="en_attente").count()
    if pend:
        out.append(f"{pend} approbation(s) en attente")
    return out


def run_daily_pipeline(session: Session, trigger: str = "manuel", use_trends: bool = True) -> dict:
    started = datetime.now(timezone.utc)
    task = Task(kind="daily_pipeline", status="en_cours", payload={"trigger": trigger})
    session.add(task)
    session.flush()
    first_log_id = (session.query(ActionLog.id).order_by(ActionLog.id.desc()).first() or (0,))[0]
    phases, errors = [], []

    def phase(num, fn):
        label = dict(PHASES)[num]
        if is_stopped(session):
            phases.append({"phase": num, "label": label, "status": "bloqué (STOP ALL)"})
            return None
        try:
            res = fn()
            phases.append({"phase": num, "label": label, "status": "terminé", "summary": res})
            return res
        except Exception as e:  # noqa: BLE001
            errors.append({"phase": num, "error": str(e)[:300]})
            phases.append({"phase": num, "label": label, "status": "erreur"})
            log_action(session, "director", f"phase_{num}", "erreur", str(e)[:300], level="A")
            return None

    def p1():
        r = scout.scan_market(session, use_trends=use_trends)
        return {"google_trends": r["google_trends"]["status"], "candidats": r["candidates"]}

    def p2():
        return {"produits_compares": len(supplier.compare_all(session))}

    def p3():
        r = scout.find_winners(session)
        return {"classes": len(r["ranked"]), "donnees_insuffisantes": len(r["insufficient_data"]),
                "top": [{"name": x["name"], "score": x["total"]} for x in r["ranked"][:5]]}

    def p4():
        r = store_builder.build_store(session)
        return {"brouillons_crees": r["drafts_created"]}

    def p5():
        log_action(session, "creative_studio", "generate_content", "non_connecte",
                   "Studio créatif non implémenté dans le MVP (aucun contenu simulé)", level="A")
        return {"statut": "non disponible dans le MVP"}

    def p6():
        r = finance.financial_report(session)
        return {k: v.get("status") for k, v in r["sources"].items()}

    def p7():
        a = _anomalies(session)
        log_action(session, "director", "monitor", "execute", f"{len(a)} anomalie(s) détectée(s)", level="A")
        return {"anomalies": a}

    def p8():
        return {"statut": "aucune optimisation automatique : les actions B/C passent par les autorisations"}

    for num, fn in [(1, p1), (2, p2), (3, p3), (4, p4), (5, p5), (6, p6), (7, p7), (8, p8)]:
        phase(num, fn)

    logs = session.query(ActionLog).filter(ActionLog.id > first_log_id).all()
    report = {
        "date": started.isoformat(), "trigger": trigger,
        "executed": [f"[{l.agent}] {l.action} : {l.message}" for l in logs if l.outcome == "execute"],
        "prepared": [f"[{l.agent}] {l.message}" for l in logs if l.outcome == "prepare"],
        "needs_approval": [{"id": a.id, "action": a.action, "montant_eur": a.amount_eur}
                           for a in session.query(Approval).filter_by(status="en_attente").all()],
        "not_connected": [f"[{l.agent}] {l.message}" for l in logs if l.outcome == "non_connecte"],
        "blocked": [f"[{l.agent}] {l.action} : {l.message}" for l in logs if l.outcome == "bloque"],
        "errors": errors,
        "data_used": {"produits": session.query(Product).count(),
                      "brouillons": session.query(ProductDraft).count()},
        "spend_eur": round(sum(l.spend_eur or 0 for l in logs), 2),
        "phases": phases,
        "next_priorities": [
            "Compléter les données manquantes des produits « données insuffisantes »",
            "Relire et compléter les brouillons (mentions « À COMPLÉTER »)",
            "Demander échantillons/certificats aux fournisseurs retenus (brouillons de demande)",
            "Connecter les intégrations nécessaires (voir onglet Connecteurs)",
        ],
    }
    phases.append({"phase": 9, "label": dict(PHASES)[9], "status": "terminé"})
    task.status = "erreur" if errors else "termine"
    task.result = report
    log_action(session, "director", "report", "execute", f"Rapport quotidien #{task.id} ({trigger})", level="A")
    return {"task_id": task.id, **report}


def latest_report(session: Session) -> dict | None:
    t = session.query(Task).filter_by(kind="daily_pipeline").order_by(Task.id.desc()).first()
    return None if t is None else {"task_id": t.id, "status": t.status, **(t.result or {})}
