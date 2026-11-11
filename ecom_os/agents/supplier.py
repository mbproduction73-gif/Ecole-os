"""Agent Supplier : comparaison des offres et préparation des demandes fournisseurs."""
from sqlalchemy.orm import Session

from ..core.logs import log_action
from ..models import Offer, Product


def offer_score(offer: Offer, sale_price: float | None) -> float:
    """Score interne 0-100 : coût rendu (40), délai (30), fiabilité (20), stock/UE (10)."""
    landed = offer.unit_cost + (offer.shipping_cost or 0)
    s_cost = 20.0 if not sale_price else max(0.0, min(40.0, (1 - landed / (sale_price / 1.21)) * 80))
    d = offer.shipping_days_max
    s_delay = 10.0 if d is None else max(0.0, 30 - max(0, d - 3) * 1.2)
    r = offer.supplier.rating
    s_rel = 8.0 if r is None else r / 5 * 20
    s_misc = (5 if offer.supplier.eu_warehouse else 0) + (5 if (offer.stock or 0) >= 100 else 0)
    return round(s_cost + s_delay + s_rel + s_misc, 1)


def rank_offers(session: Session, product: Product) -> list[dict]:
    out = []
    for o in product.offers:
        landed = round(o.unit_cost + (o.shipping_cost or 0), 2)
        out.append({"offer": o, "offer_id": o.id, "supplier": o.supplier.name, "platform": o.supplier.platform,
                    "landed_cost": landed, "days_max": o.shipping_days_max, "eu_warehouse": o.supplier.eu_warehouse,
                    "rating": o.supplier.rating, "stock": o.stock,
                    "score": offer_score(o, product.est_sale_price)})
    return sorted(out, key=lambda x: x["score"], reverse=True)


def compare_all(session: Session) -> list[dict]:
    res = []
    for p in session.query(Product).all():
        ranked = rank_offers(session, p)
        res.append({"product_id": p.id, "product": p.name,
                    "offers": [{k: v for k, v in r.items() if k != "offer"} for r in ranked]})
    log_action(session, "supplier", "compare_suppliers", "execute", f"{len(res)} produits comparés", level="A")
    return res


def prepare_supplier_request(session: Session, product: Product, supplier_name: str, kind: str = "echantillon") -> dict:
    """Prépare (sans envoyer) une demande d'échantillon/devis. L'envoi et tout achat restent manuels/approuvés."""
    body = (f"Bonjour,\n\nJe prépare le lancement d'une boutique en ligne en Belgique et je suis intéressé par "
            f"votre produit « {product.name} ».\n\nPourriez-vous me communiquer :\n"
            f"- le prix unitaire pour 1, 10 et 50 unités ;\n- les frais et délais de livraison vers la Belgique "
            f"(entrepôt UE disponible ?) ;\n- les certificats de conformité (CE, RoHS, rapports de test) et la "
            f"personne responsable dans l'UE (règlement GPSR 2023/988) ;\n- vos conditions de retour et de "
            f"remplacement ;\n- la possibilité d'une intégration API / synchronisation des commandes ;\n"
            f"- le coût d'un {kind}.\n\nCette demande n'engage aucun achat.\n\nCordialement")
    log_action(session, "supplier", "prepare_supplier_request", "prepare",
               f"Demande de {kind} préparée pour {supplier_name} (non envoyée)", level="A",
               details={"product": product.name, "supplier": supplier_name})
    return {"to": supplier_name, "subject": f"Demande de {kind} et conditions – {product.name}", "body": body,
            "status": "préparé (non envoyé)"}


def connect_supplier(session: Session) -> dict:
    """CONNECT SUPPLIER : état des intégrations fournisseurs (aucune n'est simulée)."""
    from ..connectors.registry import all_connectors
    sts = [c.status() for c in all_connectors().values() if c.category == "fournisseur"]
    log_action(session, "supplier", "read_connector", "execute", "État des intégrations fournisseurs", level="A")
    return {"suppliers_integrations": sts,
            "manual_option": "Import CSV d'offres disponible dès maintenant (onglet Fournisseurs)."}
