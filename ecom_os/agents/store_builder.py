"""Agent Store Builder : brouillons de fiches produits (FR), publication Shopify en brouillon (niveau B)."""
import html

from sqlalchemy.orm import Session

from ..connectors.base import NotConnectedError
from ..core.logs import log_action
from ..core.permissions import run_guarded
from ..models import Product, ProductDraft
from . import compliance
from .finance import margin_for_offer
from .supplier import rank_offers


def _shipping_text(offer) -> str:
    if offer and offer.shipping_days_min is not None and offer.shipping_days_max is not None:
        origin = f" depuis {offer.ships_from}" if offer.ships_from else ""
        return (f"Expédition{origin}. Délai de livraison estimé : {offer.shipping_days_min} à "
                f"{offer.shipping_days_max} jours ouvrables. Un numéro de suivi est envoyé par e-mail.")
    return "Délai de livraison : À COMPLÉTER avec le délai réel confirmé par le fournisseur."


RETURNS_TEXT = ("Vous disposez de 14 jours à compter de la réception pour vous rétracter, sans justification. "
                "Contactez-nous par e-mail pour obtenir l'adresse de retour ; le remboursement intervient au plus "
                "tard 14 jours après la rétractation (frais de retour à préciser : À COMPLÉTER). "
                "Garantie légale de conformité de 2 ans.")


def build_draft(session: Session, product: Product) -> ProductDraft:
    ranked = rank_offers(session, product)
    offer = ranked[0]["offer"] if ranked else None
    problem = product.problem_solved or "À COMPLÉTER : problème client résolu"
    target = product.target_customer or "À COMPLÉTER : client cible"
    title = product.name.strip()
    subtitle = f"Pensé pour {target.lower() if product.target_customer else target}."
    p = lambda s: f"<p>{html.escape(s)}</p>"  # noqa: E731
    desc = "".join([
        p(f"{title} répond à un besoin concret : {problem.rstrip('.')}."),
        "<h3>Pourquoi vous allez l'apprécier</h3><ul>",
        f"<li>{html.escape('Bénéfice principal : À COMPLÉTER à partir des caractéristiques vérifiées du fournisseur')}</li>",
        f"<li>{html.escape('Utilisation : À COMPLÉTER (étapes simples, démontrables en vidéo)')}</li>",
        f"<li>{html.escape('Matériaux / dimensions : À COMPLÉTER (données fournisseur vérifiées)')}</li>",
        "</ul>",
        "<h3>Livraison et retours</h3>", p(_shipping_text(offer)), p(RETURNS_TEXT),
        p("Photos : uniquement des visuels fournis/licenciés par le fournisseur ou créés par nos soins. "
          "Aucun avis client fictif."),
    ])
    faq = [
        {"q": "Quel est le délai de livraison ?", "a": _shipping_text(offer)},
        {"q": "Puis-je retourner le produit ?", "a": RETURNS_TEXT},
        {"q": "Le produit est-il conforme aux normes européennes ?",
         "a": "À COMPLÉTER après réception des certificats du fournisseur (CE/GPSR selon le produit)."},
        {"q": "Comment vous contacter ?", "a": "Par e-mail : À COMPLÉTER (adresse du service client)."},
    ]
    fin = margin_for_offer(session, product.est_sale_price, offer) if (offer and product.est_sale_price) else None
    comp = compliance.check_product(product)
    draft = ProductDraft(product_id=product.id, title=title, subtitle=subtitle, description_html=desc, faq=faq,
                         shipping_info=_shipping_text(offer), returns_info=RETURNS_TEXT,
                         price=product.est_sale_price, compliance=comp, finance=fin, status="brouillon")
    session.add(draft)
    session.flush()
    log_action(session, "store_builder", "create_draft", "prepare", f"Brouillon #{draft.id} pour « {title} »",
               level="A", details={"draft_id": draft.id, "product_id": product.id})
    return draft


def build_store(session: Session) -> dict:
    """BUILD STORE : brouillons pour les produits en shortlist (sinon rien, pas de remplissage fictif)."""
    products = session.query(Product).filter(Product.status == "shortlist").all()
    drafts = []
    for prod in products:
        if session.query(ProductDraft).filter_by(product_id=prod.id).first():
            continue
        drafts.append(build_draft(session, prod).id)
    from ..connectors.registry import get
    shop = get("shopify").status()
    return {"drafts_created": drafts, "shortlist_count": len(products), "shopify": shop,
            "next": "Relire les brouillons, compléter les « À COMPLÉTER », puis publier en brouillon Shopify "
                    "(niveau B). Le lancement public initial requiert une approbation (niveau C)."}


def publish_draft_to_shopify(session: Session, draft: ProductDraft) -> dict:
    """Crée le produit dans Shopify en statut DRAFT (invisible des clients). Niveau B."""
    from ..connectors.registry import get
    conn = get("shopify")
    if not conn.is_configured():
        log_action(session, "store_builder", "publish_product_draft", "non_connecte",
                   "Shopify non connecté : publication impossible", level="B")
        return {"status": "non connecté", "detail": str(NotConnectedError("shopify", conn.missing_env()))}
    d, res = run_guarded(session, "publish_product_draft",
                         lambda: conn.create_draft_product(draft.title, draft.description_html, draft.price),
                         agent="store_builder", payload={"draft_id": draft.id})
    if not d.allowed:
        return {"status": d.status, "detail": d.reason, "approval_id": d.approval_id}
    draft.external_id = res["id"]
    draft.status = "brouillon_shopify"
    return {"status": "exécuté", "shopify_product": res}
