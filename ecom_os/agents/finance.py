"""Agent Finance : marge contributive, seuils de rentabilité, rapport financier.

Formule (par commande, montants HT) :
  marge contributive = prix HT − coût fournisseur − livraison − frais de paiement
                       − publicité par commande − frais variables − provision retours
Seuils : CPA de rentabilité = marge avant publicité ;
         ROAS de rentabilité = prix TTC / CPA de rentabilité (ROAS mesuré sur le CA TTC,
         comme l'affichent Meta/TikTok/Google).
Aucun chiffre n'est inventé : le rapport financier n'affiche que des données de connecteurs réels.
"""
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from ..connectors.base import NotConnectedError
from ..core.logs import log_action
from ..core.state import get_setting
from ..models import ActionLog


@dataclass
class MarginInput:
    sale_price_ttc: float
    supplier_cost: float
    shipping_cost: float = 0.0
    vat_rate: float = 0.21
    payment_fee_pct: float = 0.029
    payment_fee_fixed: float = 0.25
    ads_cost_per_order: float = 0.0
    variable_fees: float = 0.0          # emballage, apps, etc. par commande
    returns_rate: float = 0.05          # part des commandes retournées/remboursées
    return_loss_ratio: float = 1.0      # part du coût marchandise+livraison perdue par retour


def compute_margin(i: MarginInput) -> dict:
    if i.sale_price_ttc <= 0:
        raise ValueError("Le prix de vente doit être > 0")
    for name in ("supplier_cost", "shipping_cost", "ads_cost_per_order", "variable_fees", "payment_fee_pct",
                 "payment_fee_fixed", "vat_rate", "returns_rate"):
        if getattr(i, name) < 0:
            raise ValueError(f"{name} ne peut pas être négatif")
    if i.returns_rate > 1:
        raise ValueError("returns_rate doit être entre 0 et 1")
    price_ht = i.sale_price_ttc / (1 + i.vat_rate)
    vat = i.sale_price_ttc - price_ht
    payment_fees = i.sale_price_ttc * i.payment_fee_pct + i.payment_fee_fixed  # frais calculés sur le TTC encaissé
    returns_provision = i.returns_rate * (i.supplier_cost + i.shipping_cost) * i.return_loss_ratio
    before_ads = price_ht - i.supplier_cost - i.shipping_cost - payment_fees - i.variable_fees - returns_provision
    contribution = before_ads - i.ads_cost_per_order
    be_cpa = before_ads
    be_roas = (i.sale_price_ttc / be_cpa) if be_cpa > 0 else None
    r = lambda x: None if x is None else round(x, 2)  # noqa: E731
    return {
        "inputs": asdict(i),
        "price_ht": r(price_ht), "vat": r(vat), "payment_fees": r(payment_fees),
        "returns_provision": r(returns_provision),
        "margin_before_ads": r(before_ads),
        "contribution_margin": r(contribution),
        "contribution_margin_pct": r(contribution / price_ht * 100),
        "break_even_cpa": r(be_cpa) if be_cpa > 0 else None,
        "break_even_roas": r(be_roas),
        "profitable": contribution > 0,
        "note": "Estimation. Vérifiez votre régime TVA (franchise PME belge possible) et vos frais réels.",
    }


def margin_for_offer(session: Session, sale_price_ttc: float, offer, ads_cost_per_order: float = 0.0,
                     returns_rate: float = 0.05) -> dict:
    return compute_margin(MarginInput(
        sale_price_ttc=sale_price_ttc, supplier_cost=offer.unit_cost, shipping_cost=offer.shipping_cost or 0,
        vat_rate=float(get_setting(session, "vat_rate")),
        payment_fee_pct=float(get_setting(session, "payment_fee_pct")),
        payment_fee_fixed=float(get_setting(session, "payment_fee_fixed")),
        ads_cost_per_order=ads_cost_per_order, returns_rate=returns_rate))


def financial_report(session: Session) -> dict:
    """Ne rapporte que des données confirmées par un connecteur réel. Sinon « non connecté »."""
    from ..connectors.registry import get
    out = {"sources": {}, "spend_recorded_eur": 0.0}
    out["spend_recorded_eur"] = round(sum(x.spend_eur or 0 for x in session.query(ActionLog).all()), 2)
    shop = get("shopify")
    try:
        out["sources"]["shopify"] = {"status": "connecté", **shop.orders_summary()}
    except NotConnectedError as e:
        out["sources"]["shopify"] = {"status": "non connecté", "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        out["sources"]["shopify"] = {"status": "erreur", "detail": str(e)}
    stripe = get("stripe")
    try:
        bal = stripe.balance()
        out["sources"]["stripe"] = {"status": "connecté", "mode": stripe.mode(),
                                    "available": bal.get("available"), "pending": bal.get("pending")}
    except NotConnectedError as e:
        out["sources"]["stripe"] = {"status": "non connecté", "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        out["sources"]["stripe"] = {"status": "erreur", "detail": str(e)}
    for key, v in out["sources"].items():
        if v["status"] == "non connecté":
            log_action(session, "finance", "read_connector", "non_connecte",
                       f"{key} non connecté : aucune donnée de ventes/encaissements", level="A")
    out["budgets"] = {"ads_eur": get_setting(session, "budget_ads_eur"),
                      "purchase_eur": get_setting(session, "budget_purchase_eur")}
    out["note"] = ("Chiffre d'affaires, encaissements et bénéfices ne sont affichés que s'ils proviennent "
                   "d'une source connectée. Aucune estimation n'est présentée comme un résultat réel.")
    log_action(session, "finance", "financial_report", "execute", "Rapport financier généré", level="A")
    return out
