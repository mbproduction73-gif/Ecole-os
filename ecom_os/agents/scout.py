"""Agent Scout : recherche de tendances et notation des produits sur 100.

Pondération : demande 25, marge 20, concurrence 15, fiabilité fournisseur 15,
logistique 15, potentiel marketing 10.
Un critère sans donnée reste vide (None). Score total calculé seulement si au moins
5 critères sur 6 sont renseignés ET que la demande et la marge sont connues ;
sinon le produit est marqué « données insuffisantes » — jamais « gagnant ».
"""
from sqlalchemy.orm import Session

from ..connectors.base import NotConnectedError
from ..core.logs import log_action
from ..models import Product
from .finance import margin_for_offer

WEIGHTS = {"demand": 25, "margin": 20, "competition": 15, "supplier": 15, "logistics": 15, "marketing": 10}
MIN_CRITERIA = 5
SHORTLIST_THRESHOLD = 65.0


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def score_demand(demand_index, growth_pct):
    if demand_index is None:
        return None
    bonus = 0.0 if growth_pct is None else clamp(growth_pct * 0.2, -15, 15)
    return round(clamp(demand_index + bonus), 1)


def score_margin(margin_pct_before_ads):
    """Marge avant pub en % du prix HT : 0 % → 0 ; 50 % ou plus → 100."""
    if margin_pct_before_ads is None:
        return None
    return round(clamp(margin_pct_before_ads * 2), 1)


def score_competition(level):
    return None if level is None else round(clamp(100 - level), 1)


def score_supplier(rating, reviews_count, api_integration=False):
    if rating is None:
        return None
    s = rating / 5 * 100
    if reviews_count is not None and reviews_count < 50:
        s -= 15  # peu d'avis vérifiables
    if api_integration:
        s += 5
    return round(clamp(s), 1)


def score_logistics(days_max, eu_warehouse=False):
    if days_max is None:
        return None
    if days_max <= 5:
        s = 100
    elif days_max <= 10:
        s = 75
    elif days_max <= 15:
        s = 50
    elif days_max <= 25:
        s = 25
    else:
        s = 0
    if eu_warehouse:
        s += 10
    return round(clamp(s), 1)


def score_marketing(potential):
    return None if potential is None else round(clamp(potential), 1)


def combine(parts: dict) -> tuple[float | None, bool]:
    known = {k: v for k, v in parts.items() if v is not None}
    sufficient = len(known) >= MIN_CRITERIA and parts.get("demand") is not None and parts.get("margin") is not None
    if not sufficient:
        return None, False
    total_w = sum(WEIGHTS[k] for k in known)
    return round(sum(v * WEIGHTS[k] for k, v in known.items()) / total_w, 1), True


def best_offer(session: Session, product: Product):
    """Offre au meilleur compromis marge / délai / fiabilité (voir agent Supplier)."""
    from .supplier import rank_offers
    ranked = rank_offers(session, product)
    return ranked[0] if ranked else None


def score_product(session: Session, product: Product) -> dict:
    notes = {}
    best = best_offer(session, product)
    offer = best["offer"] if best else None
    margin_pct = None
    if offer and product.est_sale_price:
        m = margin_for_offer(session, product.est_sale_price, offer)
        margin_pct = m["margin_before_ads"] / m["price_ht"] * 100
        notes["margin"] = f"Marge avant pub {m['margin_before_ads']} € ({margin_pct:.0f} % du HT) avec l'offre #{offer.id}"
    elif not product.est_sale_price:
        notes["margin"] = "Prix de vente envisagé manquant"
    else:
        notes["margin"] = "Aucune offre fournisseur"
    parts = {
        "demand": score_demand(product.demand_index, product.trend_growth_pct),
        "margin": score_margin(margin_pct),
        "competition": score_competition(product.competition_level),
        "supplier": score_supplier(offer.supplier.rating, offer.supplier.reviews_count,
                                   offer.supplier.api_integration) if offer else None,
        "logistics": score_logistics(offer.shipping_days_max, offer.supplier.eu_warehouse) if offer else None,
        "marketing": score_marketing(product.marketing_potential),
    }
    total, sufficient = combine(parts)
    if product.return_risk and product.return_risk.lower().startswith("elev") and total is not None:
        total = round(total - 10, 1)
        notes["return_risk"] = "Risque de retours élevé : -10"
    missing = [k for k, v in parts.items() if v is None]
    if missing:
        notes["missing"] = missing
    product.score_demand, product.score_margin = parts["demand"], parts["margin"]
    product.score_competition, product.score_supplier = parts["competition"], parts["supplier"]
    product.score_logistics, product.score_marketing = parts["logistics"], parts["marketing"]
    product.score_total, product.data_sufficient, product.score_notes = total, sufficient, notes
    if product.status in ("candidat", "analyse"):
        product.status = "analyse"
    return {"product_id": product.id, "name": product.name, "parts": parts, "total": total,
            "data_sufficient": sufficient, "notes": notes}


def refresh_trends(session: Session, limit: int = 10) -> dict:
    """Met à jour demand_index/croissance via Google Trends si disponible (données réelles uniquement)."""
    from ..connectors.registry import get
    conn = get("google_trends")
    done, errors = [], []
    if not conn.is_configured():
        log_action(session, "scout", "refresh_trends", "non_connecte", "Google Trends non connecté", level="A")
        return {"status": "non connecté", "updated": [], "errors": []}
    products = session.query(Product).filter(Product.status != "rejete").limit(limit).all()
    for p in products:
        try:
            r = conn.interest(p.keyword or p.name)
            if r["mean"] is not None:
                p.demand_index = r["mean"]
                p.trend_growth_pct = r["growth_pct"]
                done.append({"product": p.name, **r})
        except NotConnectedError:
            break
        except Exception as e:  # noqa: BLE001
            errors.append({"product": p.name, "error": str(e)[:200]})
    log_action(session, "scout", "refresh_trends", "execute" if done else ("erreur" if errors else "info"),
               f"{len(done)} produits mis à jour via Google Trends, {len(errors)} erreurs", level="A",
               details={"updated": [d["product"] for d in done], "errors": errors})
    return {"status": "connecté", "updated": done, "errors": errors}


def scan_market(session: Session, use_trends: bool = True) -> dict:
    """SCAN MARKET : état des sources de tendances + rafraîchissement des indicateurs réels."""
    from ..connectors.registry import all_connectors
    sources = [c.status() for c in all_connectors().values() if c.category == "tendances"]
    trends = refresh_trends(session) if use_trends else {"status": "ignoré"}
    log_action(session, "scout", "scan_market", "execute", "Scan des sources de tendances", level="A")
    return {"sources": sources, "google_trends": trends,
            "candidates": session.query(Product).count(),
            "hint": "Ajoutez des produits candidats (CSV ou formulaire) : le Scout ne génère pas de produits fictifs."}


def find_winners(session: Session) -> dict:
    """FIND WINNERS : note et classe ; seuls les produits avec données suffisantes sont classés."""
    results = [score_product(session, p) for p in session.query(Product).filter(Product.status != "rejete").all()]
    ranked = sorted([r for r in results if r["data_sufficient"]], key=lambda r: r["total"], reverse=True)
    insufficient = [r for r in results if not r["data_sufficient"]]
    for r in ranked:
        p = session.get(Product, r["product_id"])
        if r["total"] >= SHORTLIST_THRESHOLD:
            p.status = "shortlist"
    session.flush()
    log_action(session, "scout", "score_products", "execute",
               f"{len(ranked)} produits classés, {len(insufficient)} avec données insuffisantes", level="A")
    return {"ranked": ranked, "insufficient_data": insufficient, "threshold": SHORTLIST_THRESHOLD,
            "warning": "Un score élevé n'est pas une garantie de ventes : validez par un test réel."}
